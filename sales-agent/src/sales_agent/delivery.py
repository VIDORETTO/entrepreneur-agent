"""Public delivery cycle for durable replies.

The worker owns the lease, but it never owns the decision. Every claimed item
is checked against the current conversation and evidence immediately before an
external provider is called.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol

from .knowledge import PersistentFarolKnowledge
from .storage import StateStore
from .validation import package_capability, package_fingerprint


class DeliveryProvider(Protocol):
    def send(self, payload: Mapping[str, Any], *, idempotency_key: str) -> Mapping[str, Any]: ...


class DeliveryRejectedError(RuntimeError):
    """The provider definitively rejected a request before accepting it."""

    ambiguous = False


class DeliveryUncertainError(RuntimeError):
    """The provider outcome cannot be known locally."""

    ambiguous = True


class DeliveryProcessor:
    """Claim, revalidate, send and settle one outbox item."""

    def __init__(self, store: StateStore, *, knowledge: Optional[PersistentFarolKnowledge] = None, pilot: Any = None):
        self.store = store
        self.knowledge = knowledge or PersistentFarolKnowledge(store)
        self.pilot = pilot

    def _record_pilot(
        self,
        item: Mapping[str, Any],
        outcome: Mapping[str, Any],
        decision: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if self.pilot is not None:
            self.pilot.record(item, outcome, decision=decision)

    def revalidate(self, item: Mapping[str, Any]) -> Dict[str, Any]:
        business_id = str(item["business_id"])
        state = self.store.load_conversation(business_id, str(item["conversation_id"]), "unknown")
        package = self.store.get_business(business_id)
        if package is None:
            return {"send": False, "reason": "business_missing", "state": state}
        action = item.get("action") if isinstance(item.get("action"), Mapping) else {}
        is_transfer = action.get("type") == "human_transfer"
        if (state.get("responsible") == "human" or state.get("status") == "human_paused") and not is_transfer:
            return {"send": False, "reason": "human_takeover", "state": state}
        if state.get("status") in {"closed_without_sale", "transferred"} and not is_transfer:
            return {"send": False, "reason": "conversation_closed", "state": state}
        expected_package = item.get("package_version")
        if expected_package is not None and str(expected_package) != str(package.get("package_version")):
            return {"send": False, "reason": "package_changed", "state": state}
        expected_state = item.get("state_version")
        if expected_state is not None and int(expected_state) != int(state.get("version", 0)):
            return {"send": False, "reason": "state_changed", "state": state}
        capability_by_action = {
            "prepare_checkout": "checkout_prepare",
            "prepare_proposal": "quote",
            "human_transfer": "human_transfer",
        }
        required_capability = capability_by_action.get(str(action.get("type", "")))
        if required_capability and package_capability(package, required_capability) not in {"enabled", "assisted"}:
            return {"send": False, "reason": "capability_changed", "capability": required_capability, "state": state}
        required_capabilities = item.get("required_capabilities")
        if isinstance(required_capabilities, list):
            for capability in required_capabilities:
                if package_capability(package, str(capability)) not in {"enabled", "assisted"}:
                    return {"send": False, "reason": "capability_changed", "capability": str(capability), "state": state}
        expected_fingerprint = item.get("package_fingerprint")
        if expected_fingerprint is not None and str(expected_fingerprint) != package_fingerprint(package):
            return {"send": False, "reason": "package_changed", "state": state}
        evidence = item.get("evidence") or []
        invalid = self._invalid_evidence(business_id, evidence)
        if invalid:
            return {"send": False, "reason": "evidence_invalidated", "invalid_evidence": invalid, "state": state}
        if (
            item.get("channel") == "chatwoot"
            and item.get("channel_kind") == "whatsapp"
            and not item.get("private")
            and action.get("type") not in {"private_note", "internal_note", "human_transfer"}
            and item.get("response")
        ):
            if not self.store.buyer_window_open(business_id, str(item["conversation_id"])):
                return {"send": False, "reason": "window_closed", "state": state}
        return {"send": True, "reason": "eligible", "state": state}

    def process_claimed(self, provider: DeliveryProvider, item: Mapping[str, Any]) -> Dict[str, Any]:
        check = self.revalidate(item)
        key = str(item["message_key"])
        owner = item.get("lease_owner")
        if not owner:
            outcome = {"message_key": key, "status": "unknown", "reason": "delivery_lease_owner_missing"}
            self._record_pilot(item, outcome)
            return outcome
        pilot_decision: Optional[Mapping[str, Any]] = None
        if check["send"] and self.pilot is not None:
            decision = self.pilot.decide(item)
            pilot_decision = decision
            if not decision.get("send"):
                observed = self.store.mark_outbox_observed(
                    key, str(decision.get("reason", "pilot gate")), lease_owner=owner
                )
                outcome = {
                    "message_key": key,
                    "status": "observed" if observed else "unknown",
                    "reason": decision.get("reason") if observed else "lease_lost_before_observation",
                    "mode": decision.get("mode"),
                }
                self._record_pilot(item, outcome, pilot_decision)
                return outcome
        if not check["send"]:
            if check["reason"] == "window_closed":
                closed = self.store.close_outbox_window(item, lease_owner=str(owner))
                outcome = {
                    "message_key": key,
                    "status": "window_closed" if closed else "unknown",
                    "reason": "window_closed" if closed else "lease_lost_before_window_closure",
                }
                self._record_pilot(item, outcome, pilot_decision)
                return outcome
            cancelled = self.store.cancel_outbox_message(key, str(check["reason"]), lease_owner=owner)
            outcome = {
                "message_key": key,
                "status": "cancelled" if cancelled else "unknown",
                "reason": check["reason"] if cancelled else "lease_lost_before_cancellation",
            }
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        # A Chatwoot adapter can perform a fresh remote conversation read.  A
        # remote timeout is intentionally not retried as a send: we cannot
        # prove that a takeover/closure was absent.
        remote_check = getattr(provider, "revalidate", None)
        if check["send"] and callable(remote_check):
            try:
                remote = dict(remote_check(item))
            except Exception as exc:
                marked = self.store.mark_outbox_unknown(
                    key,
                    {"status": "unknown", "reason": "remote_state_unavailable", "error": str(exc)[:300]},
                    lease_owner=owner,
                )
                outcome = {
                    "message_key": key,
                    "status": "unknown" if marked else "unknown",
                    "reason": "remote_state_unavailable",
                }
                self._record_pilot(item, outcome, pilot_decision)
                return outcome
            if not remote.get("send", True):
                cancelled = self.store.cancel_outbox_message(key, str(remote.get("reason", "remote_state_changed")), lease_owner=owner)
                outcome = {
                    "message_key": key,
                    "status": "cancelled" if cancelled else "unknown",
                    "reason": remote.get("reason", "remote_state_changed"),
                }
                self._record_pilot(item, outcome, pilot_decision)
                return outcome
        # Revalidate ownership after every local/remote check and immediately
        # before entering the provider boundary.
        if not self.store.confirm_outbox_lease(key, str(owner)):
            outcome = {"message_key": key, "status": "unknown", "reason": "lease_lost_before_provider"}
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        prepare_send = getattr(provider, "prepare_send", None)
        if callable(prepare_send):
            try:
                prepared = bool(prepare_send(self.store, item))
            except Exception:
                prepared = False
            if not prepared:
                self.store.mark_outbox_unknown(
                    key, {"status": "unknown", "reason": "outbound_ledger_unavailable"}, lease_owner=owner
                )
                outcome = {"message_key": key, "status": "unknown", "reason": "outbound_ledger_unavailable"}
                self._record_pilot(item, outcome, pilot_decision)
                return outcome
        try:
            result = dict(provider.send(item, idempotency_key=key))
        except Exception as exc:  # provider boundary: classify without leaking payloads
            # A timeout, connection failure, or unclassified provider
            # exception may happen after the remote side accepted the request.
            # Only an explicit rejection is safe to retry.
            explicit_rejection = isinstance(exc, DeliveryRejectedError) or getattr(exc, "ambiguous", None) is False
            if explicit_rejection:
                try:
                    status = self.store.nack_outbox(key, str(exc) or "provider rejected delivery", lease_owner=owner)
                    outcome = {"message_key": key, "status": status, "reason": "provider_rejected"}
                except ValueError:
                    outcome = {"message_key": key, "status": "unknown", "reason": "lease_lost_after_provider_rejection"}
            else:
                marked = self.store.mark_outbox_unknown(
                    key,
                    {"status": "unknown", "reason": "provider_exception", "exception": type(exc).__name__},
                    lease_owner=owner,
                )
                outcome = {
                    "message_key": key,
                    "status": "unknown",
                    "reason": "provider_outcome_unknown" if marked else "lease_lost_after_provider_failure",
                }
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        if result.get("status") in {"unknown", "timeout"}:
            marked = self.store.mark_outbox_unknown(key, result, lease_owner=owner)
            outcome = {
                "message_key": key,
                "status": "unknown",
                "provider": result,
                **({} if marked else {"reason": "lease_lost_after_provider_effect"}),
            }
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        if result.get("status") not in {"sent", "confirmed", "accepted"}:
            try:
                status = self.store.nack_outbox(
                    key, str(result.get("error", "provider rejected delivery")), lease_owner=owner
                )
                outcome = {"message_key": key, "status": status, "provider": result}
            except ValueError:
                outcome = {
                    "message_key": key,
                    "status": "unknown",
                    "provider": result,
                    "reason": "lease_lost_after_provider_rejection",
                }
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        if not self.store.ack_outbox(
            key, lease_owner=owner, provider_message_id=str(result.get("provider_id") or "") or None
        ):
            outcome = {"message_key": key, "status": "unknown", "reason": "lease_lost_after_provider_effect"}
            self._record_pilot(item, outcome, pilot_decision)
            return outcome
        outcome = {"message_key": key, "status": "sent", "provider": result}
        self._record_pilot(item, outcome, pilot_decision)
        return outcome

    def process_once(self, provider: DeliveryProvider, *, limit: int = 10, lease_seconds: int = 60) -> List[Dict[str, Any]]:
        claimed = self.store.claim_outbox(limit=limit, lease_seconds=lease_seconds)
        return [self.process_claimed(provider, item) for item in claimed]

    def _invalid_evidence(self, business_id: str, evidence: Any) -> List[str]:
        if not isinstance(evidence, list):
            return []
        invalid = []
        for item in evidence:
            if not isinstance(item, Mapping):
                invalid.append("malformed")
                continue
            if not self.knowledge.evidence_is_current(
                business_id,
                str(item.get("source_id", "")),
                str(item.get("source_version", "")),
                str(item.get("evidence_id", "")),
                {field: item.get(field) for field in ("scope", "audience", "subject", "generation") if field in item},
            ):
                invalid.append(str(item.get("evidence_id", "unknown")))
        return invalid
