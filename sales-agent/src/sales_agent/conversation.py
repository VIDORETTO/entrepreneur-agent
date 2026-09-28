"""The policy-controlled conversation engine.

The engine accepts one channel event and returns a durable result. Model output
is a proposal only; every question, transition and external effect is checked
here against the active package and the connector contracts.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional
from zoneinfo import ZoneInfo

from .commerce import CommerceError, SimulatedCommerce
from .drafting import ClaimVerifier, ResponseRequirements, injection_signals
from .knowledge import KnowledgeBackend, PersistentFarolKnowledge
from .model import ModelAdapter, RuleBasedModel
from .skills import SkillCatalog
from .storage import StateStore, durable_key
from .transcription import Transcriber
from .types import EngineResult, Proposal
from .validation import package_capability, package_fingerprint


class ConversationError(ValueError):
    pass


MAX_EVENT_TEXT_LENGTH = 20_000
MAX_EVENT_ID_LENGTH = 200


class SellerEngine:
    """Deep runtime seam: one durable `handle(event)` operation."""

    def __init__(
        self,
        store: StateStore,
        *,
        model: Optional[ModelAdapter] = None,
        knowledge: Optional[KnowledgeBackend] = None,
        commerce: Optional[SimulatedCommerce] = None,
        before_send: Optional[Callable[[Mapping[str, Any], EngineResult], None]] = None,
        skill_catalog: Optional[SkillCatalog] = None,
        supervisor: Any = None,
        transcriber: Optional[Transcriber] = None,
    ):
        self.store = store
        self.model = model or RuleBasedModel()
        self.knowledge = knowledge or PersistentFarolKnowledge(store)
        self.commerce = commerce or SimulatedCommerce(store)
        self.before_send = before_send
        self.skill_catalog = skill_catalog or SkillCatalog()
        self.supervisor = supervisor
        self.transcriber = transcriber
        self._lock = threading.RLock()

    def handle(self, event: Mapping[str, Any]) -> EngineResult:
        """Process an event idempotently and persist its response before return."""

        self._validate_event(event)
        business_id = str(event["business_id"])
        conversation_id = str(event["conversation_id"])
        event_id = str(event["event_id"])
        package = self.store.get_business(business_id)
        if not package:
            raise ConversationError("negócio não configurado: %s" % business_id)

        with self._lock:
            previous = self.store.get_event(business_id, conversation_id, event_id)
            if previous:
                previous = self._confirmed_race_result(business_id, conversation_id, event_id, previous)
                previous = dict(previous)
                previous["duplicate"] = True
                return EngineResult(
                    event_id=event_id,
                    conversation_id=conversation_id,
                    response=previous["response"],
                    action=previous.get("action"),
                    state=previous.get("state", {}),
                    duplicate=True,
                    evidence=previous.get("evidence", []),
                    trace=previous.get("trace", []) + [{"type": "deduplicated_event"}],
                )

            state = self.store.load_conversation(business_id, conversation_id, str(event["contact_id"]))
            starting_version = int(state.get("version", 0))
            result = self._decide(package, state, event)
            self._maybe_draft(package, event, result)
            state = result.state
            if event.get("turn"):
                state["turn"] = dict(event["turn"])
            state["version"] = int(state.get("version", 0)) + 1
            state["last_event_id"] = event_id
            state["last_interaction"] = event.get("text", "")
            state["history"].append(
                {
                    "event_id": event_id,
                    "text": str(event.get("text", "")),
                    "response": result.response,
                    "action": result.action,
                }
            )
            state["history"] = state["history"][-40:]
            result.state = state
            if self.before_send:
                self.before_send(event, result)
            if self.supervisor is not None:
                try:
                    review = self.supervisor.observe(event, result.as_dict(), package)
                    supervisor_mode = getattr(self.supervisor, "mode", "off")
                    supervisor_policy = getattr(self.supervisor, "policy", "optional")
                    if supervisor_policy == "mandatory" and supervisor_mode != "selective":
                        # A mandatory policy has no safe meaning in
                        # observation/off mode: no correction-capable review
                        # gate exists.  Fail closed instead of treating the
                        # policy label as permission to deliver.
                        result.response = ""
                        result.action = None
                        result.state["pending"] = {
                            "type": "supervisor_review_required",
                            "reason": "mandatory_policy_requires_selective_mode",
                        }
                        result.trace.append(
                            {
                                "type": "supervisor_delivery_blocked",
                                "policy": "mandatory",
                                "reason": "mandatory_policy_requires_selective_mode",
                            }
                        )
                    elif supervisor_mode == "selective":
                        reviewer_info = review.get("reviewer", {}) if isinstance(review, Mapping) else {}
                        reviewer_result = reviewer_info.get("result", {}) if isinstance(reviewer_info, Mapping) else {}
                        revised = None
                        correction = (
                            reviewer_result.get("correction")
                            if isinstance(reviewer_result, Mapping)
                            and reviewer_info.get("status") == "completed"
                            and not reviewer_info.get("timed_out")
                            else None
                        )
                        if isinstance(correction, Mapping):
                            revised = self.supervisor.apply_selective(
                                event, result.as_dict(), package, review, correction
                            )
                            if revised.get("applied") and isinstance(revised.get("result"), Mapping):
                                candidate = revised["result"]
                                result.response = str(candidate.get("response", result.response))
                                result.action = candidate.get("action")
                                result.evidence = list(candidate.get("evidence", result.evidence))
                                result.trace = list(candidate.get("trace", result.trace))
                            elif revised.get("reason"):
                                result.trace.append(
                                    {
                                        "type": "supervisor_correction_blocked",
                                        "reason": revised["reason"],
                                        "claims": revised.get("claims", []),
                                    }
                                )
                        if getattr(self.supervisor, "policy", "optional") == "mandatory":
                            reviewer_failed = reviewer_info.get("status") != "completed" or bool(reviewer_info.get("timed_out"))
                            rejected_without_valid_correction = (
                                isinstance(reviewer_result, Mapping)
                                and reviewer_result.get("status") == "rejected"
                                and not (isinstance(revised, Mapping) and revised.get("applied"))
                            )
                            if reviewer_failed or rejected_without_valid_correction:
                                result.response = ""
                                result.action = None
                                result.state["pending"] = {
                                    "type": "supervisor_review_required",
                                    "reason": "mandatory_policy_reviewer_unavailable"
                                    if reviewer_failed
                                    else "mandatory_policy_rejected_candidate",
                                }
                                result.trace.append(
                                    {
                                        "type": "supervisor_delivery_blocked",
                                        "policy": "mandatory",
                                        "reason": result.state["pending"]["reason"],
                                    }
                                )
                    result.trace.append(
                        {
                            "type": "supervisor_observed",
                            "status": review.get("status"),
                            "candidate_id": review.get("candidate_id"),
                        }
                    )
                except Exception as exc:
                    # Optional observation is auxiliary. A mandatory policy
                    # must fail closed even if the supervisor itself cannot
                    # produce a review record.
                    if getattr(self.supervisor, "policy", "optional") == "mandatory":
                        result.response = ""
                        result.action = None
                        result.state["pending"] = {
                            "type": "supervisor_review_required",
                            "reason": "mandatory_policy_supervisor_error",
                        }
                        result.trace.append(
                            {
                                "type": "supervisor_delivery_blocked",
                                "policy": "mandatory",
                                "reason": "mandatory_policy_supervisor_error",
                            }
                        )
                    else:
                        result.trace.append({"type": "supervisor_error", "error": str(exc)[:300]})
            # The supervisor may replace or suppress the candidate after the
            # initial history entry was prepared.  Persist the delivered
            # outcome, rather than leaving a blocked or corrected response in
            # conversation memory as if it had been sent.
            if state.get("history") and state["history"][-1].get("event_id") == event_id:
                state["history"][-1]["response"] = result.response
                state["history"][-1]["action"] = result.action
            context = event.get("channel_context")
            channel_kind = context.get("channel_kind", "other") if isinstance(context, Mapping) else "other"
            payload = result.as_dict()
            commit_status, replay = self.store.commit_event(
                state,
                starting_version,
                dict(event),
                payload,
                durable_key("event", business_id, conversation_id, event_id),
                {
                    "event_id": event_id,
                    "channel": event.get("channel", "cli"),
                    "channel_kind": channel_kind,
                    "contact_id": event.get("contact_id"),
                    "response": result.response,
                    "action": result.action,
                    "state_version": state.get("version"),
                    "package_version": package.get("package_version"),
                    "package_fingerprint": package_fingerprint(package),
                    "evidence": result.evidence,
                    "candidate_id": durable_key("candidate", business_id, conversation_id, event_id),
                    "required_capabilities": self._required_capabilities(result),
                    "defer_delivery": (result.state.get("pending") or {}).get("type") == "effect_in_progress",
                },
            )
            if commit_status == "duplicate":
                replay = replay or payload
                replay = self._confirmed_race_result(business_id, conversation_id, event_id, replay)
                if replay.get("action") is None and (replay.get("state", {}).get("pending") or {}).get("type") == "effect_in_progress":
                    effect_key = (replay.get("state", {}).get("pending") or {}).get("effect_key")
                    if effect_key:
                        current_effect = self.commerce.query_effect(str(effect_key))
                        if current_effect and current_effect.get("status") == "confirmed":
                            replay = self.store.get_event(business_id, conversation_id, event_id) or replay
                return EngineResult(
                    event_id=event_id,
                    conversation_id=conversation_id,
                    response=replay["response"],
                    action=replay.get("action"),
                    state=replay.get("state", state),
                    duplicate=True,
                    evidence=replay.get("evidence", []),
                    trace=replay.get("trace", []) + [{"type": "deduplicated_race"}],
                )
            if commit_status == "stale":
                # A correction or human takeover won while this response was
                # being prepared. Persist the event for audit, but do not put
                # the stale response or effect in the outbox.
                stale_action = result.action
                pending_effect_key = (result.state.get("pending") or {}).get("effect_key")
                original_trace = list(result.trace)
                for _ in range(5):
                    latest = self.store.load_conversation(business_id, conversation_id, str(event["contact_id"]))
                    latest_version = int(latest.get("version", 0))
                    result.state = latest
                    result.response = ""
                    result.action = None
                    reconciled_state = None
                    if stale_action is not None:
                        effect_key = stale_action.get("effect_key")
                        quote_id = stale_action.get("quote_id")
                        current_effect = self.commerce.query_effect(str(effect_key)) if effect_key else None
                        effect_status = str((current_effect or {}).get("status", "unknown"))
                        operation_type = "checkout" if stale_action.get("type") == "prepare_checkout" else stale_action.get("type")
                        latest["phase"] = "action_in_progress"
                        if effect_status == "confirmed":
                            # The stale worker lost the conversation CAS after
                            # its idempotent effect was already confirmed.  Do
                            # not manufacture an unknown operation or enqueue a
                            # second checkout.
                            effect_conflicts = self._confirmed_effect_conflicts_with_state(current_effect or {}, latest)
                            latest["pending"] = (
                                {
                                    "type": "post_effect_correction",
                                    "reason": "correction conflicts with confirmed external effect",
                                    "effect": stale_action,
                                    "effect_key": effect_key,
                                }
                                if effect_conflicts
                                else None
                            )
                            if effect_conflicts:
                                latest["follow_up_allowed"] = False
                            latest["operation"] = {
                                "type": operation_type,
                                **dict(current_effect or {}),
                                "status": "confirmed",
                                "effect_key": effect_key,
                            }
                        elif effect_status == "reserved":
                            latest["pending"] = {
                                "type": "effect_in_progress",
                                "effect_key": effect_key,
                                "reason": "idempotent effect is still being completed",
                            }
                            latest["operation"] = {
                                "type": operation_type,
                                "status": "pending",
                                "effect_key": effect_key,
                                "quote_id": quote_id,
                            }
                        else:
                            latest["pending"] = {
                                "type": "post_effect_correction",
                                "reason": "correction arrived after external effect",
                                "effect": stale_action,
                                "effect_key": effect_key,
                            }
                            latest["operation"] = {
                                "type": operation_type,
                                "status": "unknown",
                                "effect_key": effect_key,
                                "quote_id": quote_id,
                                "effect": stale_action,
                            }
                        latest["version"] = latest_version + 1
                        reconciled_state = latest
                        if effect_status == "confirmed":
                            result.response = (
                                "A operação já foi preparada, mas a correção conflita com o efeito confirmado. "
                                "Vou manter o pedido bloqueado até a conciliação; não vou duplicar o checkout."
                                if reconciled_state and reconciled_state.get("pending")
                                else "A operação já foi preparada e permanece registrada sem duplicação."
                            )
                        else:
                            result.response = "A condição mudou enquanto eu processava. A operação foi registrada para conciliação antes de qualquer novo passo."
                    result.trace = original_trace + [
                        {
                            "type": "stale_response_suppressed",
                            "starting_version": starting_version,
                            "current_version": latest.get("version"),
                        }
                    ]
                    stale_message_key = durable_key("event", business_id, conversation_id, event_id)
                    stale_status, stale_replay = self.store.commit_stale_event(
                        dict(event),
                        result.as_dict(),
                        reconciled_state=reconciled_state,
                        expected_version=latest_version if reconciled_state is not None else None,
                        message_key=stale_message_key,
                        outbox_payload={
                            "event_id": event_id,
                            "channel": event.get("channel", "cli"),
                            "channel_kind": channel_kind,
                            "contact_id": event.get("contact_id"),
                            "response": result.response,
                            "action": result.action,
                            "state_version": result.state.get("version"),
                            "package_version": package.get("package_version"),
                            "package_fingerprint": package_fingerprint(package),
                            "evidence": result.evidence,
                            "candidate_id": durable_key("candidate", business_id, conversation_id, event_id),
                            "required_capabilities": self._required_capabilities(result),
                            "defer_delivery": (result.state.get("pending") or {}).get("type") == "effect_in_progress",
                        },
                    )
                    if stale_status == "committed":
                        if stale_action is None and pending_effect_key:
                            effect = self.commerce.query_effect(str(pending_effect_key))
                            if effect and effect.get("status") == "confirmed":
                                stored = self.store.get_event(business_id, conversation_id, event_id)
                                if stored and stored.get("action"):
                                    return EngineResult(event_id=event_id, conversation_id=conversation_id,
                                                        response=stored["response"], action=stored["action"],
                                                        state=stored.get("state", result.state),
                                                        evidence=stored.get("evidence", []), trace=stored.get("trace", []))
                        return result
                    if stale_status == "duplicate":
                        stale_replay = stale_replay or result.as_dict()
                        stale_replay = self._confirmed_race_result(business_id, conversation_id, event_id, stale_replay)
                        return EngineResult(
                            event_id=event_id,
                            conversation_id=conversation_id,
                            response=stale_replay["response"],
                            action=stale_replay.get("action"),
                            state=stale_replay.get("state", latest),
                            duplicate=True,
                            evidence=stale_replay.get("evidence", []),
                            trace=stale_replay.get("trace", []) + [{"type": "deduplicated_stale_race"}],
                        )
                raise ConversationError("a conversa mudou repetidamente durante a conciliação; tente novamente")
            if (result.state.get("pending") or {}).get("type") == "effect_in_progress":
                deadline = time.monotonic() + 0.2
                while time.monotonic() < deadline:
                    recorded = self.store.get_event(business_id, conversation_id, event_id)
                    if recorded and recorded.get("action"):
                        return EngineResult(event_id=event_id, conversation_id=conversation_id,
                                            response=recorded["response"], action=recorded["action"],
                                            state=recorded.get("state", result.state),
                                            evidence=recorded.get("evidence", []), trace=recorded.get("trace", []))
                    time.sleep(0.005)
            return result

    def _confirmed_race_result(self, business_id: str, conversation_id: str, event_id: str,
                               recorded: Mapping[str, Any]) -> Mapping[str, Any]:
        if recorded.get("action"):
            return recorded
        pending = (recorded.get("state") or {}).get("pending") or {}
        if pending.get("type") != "effect_in_progress" or not pending.get("effect_key"):
            return recorded
        effect = self.commerce.query_effect(str(pending["effect_key"]))
        if not effect or effect.get("status") != "confirmed":
            return recorded
        current = self.store.get_event(business_id, conversation_id, event_id)
        return current if current and current.get("action") else recorded

    def resume(
        self,
        business_id: str,
        conversation_id: str,
        *,
        contact_id: str,
        authority: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Release a human pause only through an explicit operator action."""

        for name, value in (("business_id", business_id), ("conversation_id", conversation_id), ("contact_id", contact_id), ("authority", authority), ("reason", reason)):
            if not isinstance(value, str) or not value.strip():
                raise ConversationError("retomada sem campo obrigatório: %s" % name)
        with self._lock:
            state = self.store.load_conversation(business_id, conversation_id, contact_id)
            if state.get("responsible") != "human" and state.get("status") != "human_paused":
                return {"resumed": False, "reason": "conversation_not_human_paused", "state": state}
            expected_version = int(state.get("version", 0))
            state["responsible"] = "ai"
            state["status"] = "active"
            state["pending"] = None
            state["phase"] = "action_in_progress" if (state.get("operation") or {}).get("status") in {"pending", "unknown"} else "exploring"
            state["follow_up_allowed"] = (state.get("operation") or {}).get("status") not in {"unknown", "pending"}
            state["resume_control"] = {
                "authority": authority,
                "reason": reason,
                "explicit": True,
            }
            state.setdefault("history", []).append(
                {"type": "human_pause_resumed", "authority": authority, "reason": reason}
            )
            state["history"] = state["history"][-40:]
            state["version"] = expected_version + 1
            if not self.store.save_conversation_if_version(state, expected_version):
                raise ConversationError("a conversa mudou durante a retomada; tente novamente")
            return {"resumed": True, "reason": "explicit_authorization", "state": state}

    def schedule_follow_up(self, business_id: str, conversation_id: str, task_id: str, message: str) -> Dict[str, Any]:
        """Queue a follow-up intent; sending is revalidated at the call site."""
        state = self.store.load_conversation(business_id, conversation_id, "unknown")
        package = self.store.get_business(business_id) or {}
        capability_allowed = package_capability(package, "follow_up") in {"enabled", "assisted"}
        eligible = capability_allowed and self._follow_up_eligible(state)
        latest = self.store.latest_buyer_message(business_id, conversation_id)
        context = (latest or {}).get("event", {}).get("channel_context", {})
        payload = {"task_id": task_id, "message": message, "status": "scheduled"}
        if latest is not None:
            payload.update({"channel": "chatwoot", "channel_kind": context.get("channel_kind", "other"), "response": message})
        scheduled = self.store.enqueue_message(
            durable_key("followup", business_id, conversation_id, task_id),
            business_id,
            conversation_id,
            payload,
        ) if eligible else False
        reason = "eligible" if eligible else ("capability disabled" if not capability_allowed else "conversation not eligible")
        return {"scheduled": scheduled, "task_id": task_id, "eligible_now": eligible, "reason": reason}

    def revalidate_follow_up(self, business_id: str, conversation_id: str, task_id: str) -> Dict[str, Any]:
        """Recheck the persisted conversation immediately before delivery."""
        state = self.store.load_conversation(business_id, conversation_id, "unknown")
        package = self.store.get_business(business_id) or {}
        capability_allowed = package_capability(package, "follow_up") in {"enabled", "assisted"}
        eligible = capability_allowed and self._follow_up_eligible(state)
        reason = "eligible" if eligible else ("capability disabled" if not capability_allowed else "conversation no longer eligible")
        if eligible:
            latest = self.store.latest_buyer_message(business_id, conversation_id)
            context = (latest or {}).get("event", {}).get("channel_context", {})
            if context.get("channel_kind") == "whatsapp" and not self.store.buyer_window_open(business_id, conversation_id):
                eligible = False
                reason = "window_closed"
        if not eligible:
            self.store.cancel_followup(business_id, conversation_id, task_id)
        return {"task_id": task_id, "send": eligible, "reason": reason, "responsible": state.get("responsible")}

    @staticmethod
    def _follow_up_eligible(state: Mapping[str, Any]) -> bool:
        return bool(
            state.get("follow_up_allowed")
            and state.get("responsible") == "ai"
            and state.get("status") == "active"
            and state.get("phase") not in {"concluído", "encerrado_sem_venda", "transferido"}
            and (state.get("operation") or {}).get("type") in {None, "none"}
        )

    @staticmethod
    def _validate_event(event: Mapping[str, Any]) -> None:
        for field in ("business_id", "conversation_id", "event_id", "contact_id", "text"):
            value = event.get(field)
            if not isinstance(value, str) or (not value.strip() and not (field == "text" and event.get("attachments"))):
                raise ConversationError("evento sem campo obrigatório: %s" % field)
            limit = MAX_EVENT_TEXT_LENGTH if field == "text" else MAX_EVENT_ID_LENGTH
            if len(value) > limit:
                raise ConversationError("campo do evento excede o limite: %s" % field)
        channel = event.get("channel", "cli")
        if not isinstance(channel, str) or not channel.strip() or len(channel) > 100:
            raise ConversationError("channel inválido")

    def _decide(self, package: Mapping[str, Any], state: Dict[str, Any], event: Mapping[str, Any]) -> EngineResult:
        text = str(event["text"])
        trace: List[Dict[str, Any]] = []
        signals = injection_signals(text)
        if signals:
            trace.append({"type": "injection_signal", "source": "buyer", "signals": signals})
        evidence: List[Dict[str, Any]] = []
        action: Optional[Dict[str, Any]] = None
        objection_response: Optional[str] = None
        state.setdefault(
            "memory",
            {"facts": {}, "fact_history": [], "open_questions": [], "answered_fields": [], "objective": state.get("intent", "unknown")},
        )

        # Chatwoot events must come from the authenticated admission ledger
        # for every response, not only for checkout.  A forged event must not
        # be able to ask the model to disclose catalog/knowledge or pause a
        # real conversation.  The safe result is audited locally without an
        # outbox intent.
        if str(event.get("channel", "")) == "chatwoot" and not self._identity_verified(event):
            state["pending"] = {
                "type": "channel_authentication_required",
                "reason": "evento Chatwoot não foi admitido pela entrada autenticada",
            }
            return self._result(
                event,
                state,
                "",
                trace=[{"type": "channel_event_rejected", "reason": "authentication_required"}],
            )

        # A human owner has precedence over every model proposal.
        if state.get("responsible") == "human" or state.get("status") == "human_paused":
            return EngineResult(
                event_id=str(event["event_id"]),
                conversation_id=str(event["conversation_id"]),
                response="",
                state=state,
                trace=[{"type": "human_pause_respected"}],
            )

        attachments = event.get("attachments") if isinstance(event.get("attachments"), list) else []
        if attachments:
            state["attachments"] = [
                {key: item.get(key) for key in ("type", "mime", "size")}
                for item in attachments
                if isinstance(item, Mapping)
            ][:8]
        transcribed = False
        if attachments and not text.strip() and self.transcriber is not None:
            audio = next((item for item in attachments if isinstance(item, Mapping) and item.get("type") == "audio"), None)
            url = audio.get("url") if audio is not None else None
            if isinstance(url, str):
                try:
                    transcript = self.transcriber.transcribe(url)
                except Exception:
                    transcript = ""
                if isinstance(transcript, str) and 0 < len(transcript.strip()) <= MAX_EVENT_TEXT_LENGTH:
                    text = transcript.strip()
                    transcribed = True
                    trace.append({"type": "transcribed", "source": "audio"})
        if attachments and not text.strip():
            policy = str(package.get("non_text_policy", "ask_text"))
            response = (
                "Posso chamar um atendente para ajudar com este anexo."
                if policy == "offer_human"
                else "Recebi o anexo. Pode enviar sua pergunta em texto?"
            )
            state["pending"] = {"type": "non_text_message", "reason": "content_unavailable"}
            return self._result(event, state, response, trace=[{"type": "non_text_policy", "policy": policy}])

        skill_selection = self.skill_catalog.select(package, text, state)
        skill_trace = {
            "type": "skills_selected",
            "declared": skill_selection["declared"],
            "available": skill_selection["available"],
            "selected": skill_selection["selected"],
            "context_prepared": skill_selection["context_prepared"],
            "applied": skill_selection["applied"],
            "sent_to_model": skill_selection["sent_to_model"],
            # The runtime can only report this after an adapter explicitly
            # returns the observation; preparation is not evidence of model
            # application.
            "model_observed_applied": None,
            "unavailable": skill_selection["unavailable"],
            "budget": skill_selection["budget"],
        }
        trace.append(skill_trace)
        if skill_selection["unavailable"]:
            trace.append(
                {
                    "type": "skills_degraded",
                    "reasons": skill_selection["unavailable"],
                    "model_mode": getattr(self.model, "name", "unknown"),
                }
            )
        runtime_package = dict(package)
        runtime_package["_buyer_skill_context"] = self.skill_catalog.context(skill_selection)
        try:
            proposal = self.model.propose(text, runtime_package, state)
        except Exception:
            state["pending"] = {"type": "model_unavailable", "reason": "proposal_failed"}
            trace.append({"type": "model_error", "model": getattr(self.model, "name", "unknown")})
            return self._result(
                event,
                state,
                "Não consegui validar esta mensagem agora. Não vou inventar uma condição nem executar uma operação; tente novamente ou peça atendimento humano.",
                trace=trace,
            )
        skill_trace["model_observed_applied"] = self._model_observed_skills(proposal)
        trace.append(
            {
                "type": "model_proposal",
                "model": proposal.model_name,
                "intent": proposal.intent,
                "offer_id": proposal.offer_id,
                "requested_action": proposal.requested_action,
                "topics": list(proposal.topics),
                "profile": proposal.raw.get("profile") if isinstance(proposal.raw, Mapping) else None,
                "model_calls": proposal.raw.get("model_calls") if isinstance(proposal.raw, Mapping) else None,
                "usage": proposal.raw.get("usage") if isinstance(proposal.raw, Mapping) else None,
                "cost": proposal.raw.get("cost") if isinstance(proposal.raw, Mapping) else None,
                "latency_ms": proposal.raw.get("latency_ms") if isinstance(proposal.raw, Mapping) else None,
            }
        )
        if proposal.intent == "unknown" and not proposal.offer_id and not proposal.topics:
            state["fallback_count"] = int(state.get("fallback_count", 0)) + 1
            if state["fallback_count"] >= int(package.get("loop_policy", {}).get("fallback_limit", 2)) + 1:
                state["pending"] = {"type": "human_offer", "reason": "loop_detected"}
                return self._result(event, state, "Posso chamar uma pessoa para ajudar. Quer falar com um atendente?",
                                    trace=trace + [{"type": "loop_detected", "reason": "repeated_fallback"}])
        else:
            state["fallback_count"] = 0
        if re.search(r"já falei|ja falei|você não entende|voce nao entende|cansei de repetir", text.casefold()) and proposal.intent != "human":
            state["pending"] = {"type": "human_offer", "reason": "frustration"}
            return self._result(event, state, "Entendo. Posso chamar uma pessoa para ajudar.",
                                trace=trace + [{"type": "loop_detected", "reason": "frustration"}])
        if isinstance(proposal.raw, Mapping) and proposal.raw.get("model_contract_failed"):
            trace.append({"type": "model_contract_failed", "model": proposal.model_name, "calls": proposal.raw.get("model_calls")})
            if proposal.raw.get("model_timeout"):
                trace.append({"type": "model_timeout", "model": proposal.model_name})
            state["pending"] = {"type": "model_contract_failed", "reason": "proposal_invalid"}
            return self._result(
                event,
                state,
                "Não consegui validar o pedido com segurança. Posso ajudar com informações ou chamar um atendente.",
                trace=trace,
            )
        offer = self._offer(package, proposal.offer_id)
        if proposal.offer_id and not offer:
            trace.append({"type": "proposal_rejected", "reason": "offer_not_in_package"})
            proposal.offer_id = None
        pending_type = (state.get("pending") or {}).get("type")
        if proposal.intent in {"buy", "update", "unknown"} and (
            pending_type in {"reconcile_checkout", "post_effect_correction"}
            or (state.get("operation") or {}).get("status") == "unknown"
        ):
            return self._result(
                event,
                state,
                "Existe uma operação com resultado pendente de conciliação. Não vou alterar o pedido nem iniciar outro checkout antes de resolvê-la.",
                trace=trace + [{"type": "effect_reconciliation_required"}],
            )
        self._merge_safe_facts(state, proposal, offer, trace, event_id=str(event["event_id"]))

        # A profile is a durable scope decision, not a hint for the model.
        # A later bare update such as "tamanho M" must not turn a support,
        # financial, post-sale, or informational conversation back into a
        # checkout. Only an explicit commercial resumption can leave one of
        # those profiles.
        limited_profiles = {"support", "post_sale", "financial", "informational"}
        current_profile = str(state.get("profile", "commercial"))
        if current_profile in limited_profiles and proposal.intent in {"buy", "update"}:
            if self._explicit_commercial_resume(text, proposal, state):
                state["profile"] = "commercial"
                state["pending"] = None
                state["memory"]["objective"] = "commercial"
                trace.append(
                    {
                        "type": "profile_commercial_resume",
                        "from": current_profile,
                        "source": "explicit_buyer_request",
                    }
                )
            else:
                state["pending"] = {
                    "type": "profile_scope",
                    "profile": current_profile,
                    "reason": "commercial_resume_required",
                }
                trace.append(
                    {
                        "type": "profile_limit_enforced",
                        "profile": current_profile,
                        "intent": proposal.intent,
                        "reason": "commercial_resume_required",
                    }
                )
                return self._result(
                    event,
                    state,
                    "Este atendimento está no perfil %s. Não vou abrir checkout a partir de uma atualização isolada; diga explicitamente que quer retomar a compra se isso for o que deseja."
                    % current_profile.replace("_", "-"),
                    trace=trace,
                )

        if proposal.intent in {"post_sale", "support", "financial"}:
            previous_profile = state.get("profile", "commercial")
            state["profile"] = (
                "post_sale" if proposal.intent == "post_sale" else "financial" if proposal.intent == "financial" else "support"
            )
            state["intent"] = proposal.intent
            state["memory"]["objective"] = proposal.intent
            state["pending"] = {
                "type": "financial_scope" if proposal.intent == "financial" else "support_scope",
                "reason": "profile_limits_commercial_actions",
            }
            trace.append(
                {
                    "type": "profile_transition",
                    "from": previous_profile,
                    "to": state["profile"],
                    "source": "buyer_intent",
                }
            )
            return self._result(
                event,
                state,
                (
                    "Entendi. Vou tratar esta conversa como financeira e não vou abrir checkout, confirmar pagamento ou prometer estorno sem o provedor."
                    if proposal.intent == "financial"
                    else "Entendi. Vou tratar esta conversa como suporte/pós-venda e manter o atendimento dentro desse escopo. Posso registrar o problema e consultar a documentação aprovada."
                ),
                trace=trace,
            )

        if proposal.intent == "preference":
            conversation_policy = package.get("policies", {}).get("conversation", {})
            transitions = conversation_policy.get("preference_transitions", []) if isinstance(conversation_policy, Mapping) else []
            normalized_text = text.casefold()
            selected = next(
                (
                    item
                    for item in transitions
                    if isinstance(item, Mapping)
                    and any(str(term).casefold() in normalized_text for term in item.get("terms", []))
                ),
                None,
            )
            if selected is None:
                state["pending"] = {"type": "preference_review", "reason": "preference_not_configured"}
                return self._result(
                    event,
                    state,
                    "Registrei sua preferência, mas ela ainda não está configurada para mudar o atendimento automaticamente.",
                    trace=trace + [{"type": "preference_unconfigured"}],
                )
            previous_profile = state.get("profile", "commercial")
            profile = str(selected.get("profile", "commercial"))
            source = str(selected.get("source", "package-policy"))
            state["profile"] = profile
            state["intent"] = str(selected.get("objective", "information"))
            state["pending"] = None
            state["memory"]["objective"] = state["intent"]
            state["memory"]["preference"] = {
                "id": str(selected.get("id", "configured-preference")),
                "value": proposal.facts.get("preference", text),
                "source": source,
                "event_id": str(event["event_id"]),
            }
            trace.append(
                {
                    "type": "preference_transition",
                    "from": previous_profile,
                    "to": profile,
                    "preference_id": state["memory"]["preference"]["id"],
                    "source": source,
                }
            )
            return self._result(
                event,
                state,
                "Entendi. Vou manter o atendimento no modo informativo configurado, sem preparar uma operação de compra automaticamente.",
                trace=trace,
            )

        if proposal.intent == "objection":
            state["intent"] = "objection"
            if offer and offer.get("price_type", "fixed") == "fixed" and "price" in proposal.topics:
                amount = float(offer["price"])
                suffix = " por unidade" if offer.get("kind") == "physical" else ""
                trace.append(
                    {
                        "type": "objection_handled",
                        "conditions_source": "approved_package",
                        "offer_id": offer["id"],
                    }
                )
                trace.append(
                    {
                        "type": "unsupported_objection_claim_blocked",
                        "claims": ["discount", "urgency"],
                    }
                )
                objection_response = (
                    "Entendo a preocupação. A condição aprovada é R$ %.2f%s. "
                    "Não há desconto aprovado nesta configuração; não vou inventar uma condição comercial."
                    % (amount, suffix)
                )
                if len(proposal.topics) <= 1:
                    return self._result(event, state, objection_response, trace=trace)
                # Price is already answered by the structured offer.  Keep all
                # other requested topics for the evidence path instead of
                # letting the objection short-circuit the buyer's question.
                proposal.topics = [topic for topic in proposal.topics if topic != "price"]
            trace.append({"type": "objection_handled", "conditions_source": "approved-evidence"})
            proposal.intent = "knowledge"

        if proposal.intent == "stop":
            self.store.cancel_pending_deliveries(
                str(package["business"]["id"]), str(state["conversation_id"]), "cancelled by buyer refusal"
            )
            self.store.cancel_followups(str(package["business"]["id"]), str(state["conversation_id"]))
            state["follow_up_allowed"] = False
            state["responsible"] = "ai"
            state["status"] = "closed_without_sale"
            state["phase"] = "encerrado_sem_venda"
            state["pending"] = None
            return self._result(event, state, "Entendido. Não vou enviar novas mensagens comerciais.", trace=trace)

        if proposal.intent == "human":
            self.store.cancel_pending_deliveries(
                str(package["business"]["id"]), str(state["conversation_id"]), "cancelled by human takeover"
            )
            self.store.cancel_followups(str(package["business"]["id"]), str(state["conversation_id"]))
            pending_context = state.get("pending")
            state["responsible"] = "human"
            state["status"] = "human_paused"
            state["phase"] = "transferido"
            state["pending"] = None
            if package_capability(package, "human_transfer") not in {"enabled", "assisted"}:
                state["pending"] = {"type": "human_transfer_unavailable", "context": pending_context}
                return self._result(
                    event,
                    state,
                    "Pausei as respostas automáticas, mas este negócio ainda não tem uma fila humana habilitada.",
                    trace=trace + [{"type": "capability_blocked", "capability": "human_transfer"}],
                )
            action = {
                "type": "human_transfer",
                "status": "queued",
                "context": {
                    "objective": state.get("intent"),
                    "facts": dict(state.get("facts", {})),
                    "operation": dict(state.get("operation", {})),
                    "pending": pending_context,
                },
            }
            response = "Vou encaminhar você para uma pessoa, sem pedir outra qualificação."
            response += self._service_hours_message(package)
            return self._result(event, state, response, action, trace)

        if proposal.intent == "thanks":
            response = "Por nada!"
            if state.get("status") == "closed_without_sale":
                response = "Por nada!"
            return self._result(event, state, response, trace=trace)

        # A new explicit purchase after a finished interaction opens a new operation,
        # while keeping the historical record intact.
        if state.get("status") == "closed_without_sale" and proposal.intent in {"buy", "update"}:
            state["status"] = "active"
            state["phase"] = "exploring"
            state["responsible"] = "ai"
            state["operation"] = {"type": "none", "status": "none"}
            state["quote"] = None
            state["pending"] = None
            state["follow_up_allowed"] = True
            trace.append({"type": "new_operation_after_close"})

        if proposal.intent == "price":
            if not offer:
                return self._result(event, state, "Qual oferta você quer consultar?", trace=trace)
            if package_capability(package, "catalog_query") not in {"enabled", "assisted"}:
                state["pending"] = {"type": "catalog_disabled"}
                return self._result(
                    event,
                    state,
                    "A consulta de catálogo ainda não está habilitada para este negócio; não vou informar um valor não aprovado.",
                    trace=trace + [{"type": "capability_blocked", "capability": "catalog_query"}],
                )
            if offer.get("price_type", "fixed") != "fixed":
                question = self._first_missing(offer, state["facts"])
                return self._ask(event, state, offer, question, "o valor depende desse escopo", trace)
            amount = float(offer["price"])
            suffix = " por unidade" if offer.get("kind") == "physical" else ""
            conditions = offer.get("description", "")
            response = "O %s custa R$ %.2f%s." % (offer["name"], amount, suffix)
            if conditions:
                response += " " + conditions
            return self._result(event, state, response, trace=trace)

        if proposal.intent == "knowledge":
            if package_capability(package, "knowledge_query") not in {"enabled", "assisted"}:
                state["pending"] = {"type": "knowledge_disabled"}
                return self._result(
                    event,
                    state,
                    "A consulta de conhecimento ainda não está habilitada para este negócio; não vou responder sem uma fonte aprovada.",
                    trace=trace + [{"type": "capability_blocked", "capability": "knowledge_query"}],
                )
            if not offer:
                offer = self._offer(package, state.get("facts", {}).get("offer_id"))
            business_id = str(package["business"]["id"])
            declared_topics = list(proposal.topics)
            # A generic fallback is not evidence. If an adapter omitted the
            # requested topic (or returned only the legacy ``general``
            # placeholder), fail closed and record the ambiguity explicitly.
            topics = [topic for topic in declared_topics if topic != "general"]
            if not topics:
                state["pending"] = {
                    "type": "evidence",
                    "reason": "no_authorized_source",
                    "missing_topics": [],
                }
                return self._result(
                    event,
                    state,
                    "Não consegui identificar uma condição específica para consultar. Vou registrar a lacuna sem usar uma fonte genérica ou inventar uma resposta.",
                    trace=trace + [{"type": "evidence_topic_missing", "declared_topics": declared_topics}],
                )
            responses: List[str] = [objection_response] if objection_response else []
            missing_topics: List[str] = []
            conflict_topics: List[str] = []
            used_trace = list(trace)
            for topic in topics:
                if topic == "price":
                    if offer and offer.get("price_type", "fixed") == "fixed":
                        amount = float(offer["price"])
                        suffix = " por unidade" if offer.get("kind") == "physical" else ""
                        responses.append("O %s custa R$ %.2f%s." % (offer["name"], amount, suffix))
                    else:
                        missing_topics.append(topic)
                    continue
                query = "%s %s" % (topic, text)
                search_kwargs = {"audience": "buyer"}
                if offer:
                    search_kwargs["scope"] = str(offer.get("id", ""))
                hits = [
                    hit
                    for hit in self.knowledge.search(business_id, query, 5, **search_kwargs)
                    if not hit.get("subject") or str(hit.get("subject")) == topic
                    if self._evidence_covers_topic(topic, hit)
                ]
                safe_hits = []
                for hit in hits:
                    source_signals = injection_signals(str(hit.get("content", "")))
                    if source_signals:
                        used_trace.append({"type": "injection_signal", "source": "evidence",
                                           "evidence_id": hit.get("evidence_id"), "signals": source_signals})
                    else:
                        safe_hits.append(hit)
                hits = safe_hits
                if not hits:
                    missing_topics.append(topic)
                    continue
                if self._material_conflict(hits):
                    conflict_topics.append(topic)
                    continue
                chosen = hits[0]
                evidence.append(dict(chosen))
                responses.append(self._evidence_answer(text, chosen["content"]))
                used_trace.append({"type": "evidence_used", "topic": topic, "evidence_id": chosen["evidence_id"]})
            if conflict_topics:
                state["pending"] = {"type": "evidence", "reason": "material_conflict", "topics": conflict_topics}
                return self._result(
                    event,
                    state,
                    "Encontrei condições conflitantes e não vou escolher uma arbitrariamente. Preciso confirmar qual política está vigente.",
                    trace=used_trace + [{"type": "evidence_conflict", "topics": conflict_topics}],
                    evidence=evidence,
                )
            if missing_topics:
                state["pending"] = {
                    "type": "evidence",
                    "reason": "partial_coverage" if responses else "no_authorized_source",
                    "missing_topics": missing_topics,
                }
                labels = ", ".join(self._topic_label(topic) for topic in missing_topics)
                if responses:
                    response = " ".join(responses) + " Sobre %s, não encontrei uma condição documentada e aprovada agora." % labels
                else:
                    response = "Não encontrei uma fonte aprovada para confirmar %s agora. Vou registrar a lacuna sem inventar uma resposta." % labels
                return self._result(
                    event,
                    state,
                    response,
                    trace=used_trace + [{"type": "evidence_missing", "topics": missing_topics}],
                    evidence=evidence,
                )
            return self._result(event, state, " ".join(responses), trace=used_trace, evidence=evidence)

        if proposal.intent == "payment_proof":
            state["pending"] = {"type": "payment_verification", "reason": "customer-provided proof is not provider confirmation"}
            state["operation"] = {**state.get("operation", {}), "payment_status": "pending"}
            return self._result(
                event,
                state,
                "Recebi o comprovante, mas ainda não posso marcar o pagamento como confirmado. Vou consultar o provedor ou encaminhar para conferência.",
                trace=trace + [{"type": "payment_proof_not_confirmation"}],
            )

        # A pending missing field or quote confirmation turns a terse update into
        # the same buying operation; it never starts a generic discovery funnel.
        if proposal.intent in {"update", "unknown"} and (state.get("pending") or state.get("quote")):
            proposal.intent = "buy"
            trace.append({"type": "pending_operation_continued"})

        if proposal.intent == "buy":
            if transcribed:
                state["pending"] = {"type": "transcribed_confirmation", "reason": "text_confirmation_required"}
                return self._result(
                    event,
                    state,
                    "Entendi seu pedido no áudio. Confirma por texto antes de eu preparar a compra?",
                    trace=trace + [{"type": "transcribed_action_blocked"}],
                )
            return self._buy(package, state, event, proposal, trace)

        if proposal.intent == "greeting":
            return self._result(event, state, "Olá. O que você gostaria de comprar ou consultar?", trace=trace)
        return self._result(event, state, "Posso ajudar com uma oferta, preço, prazo ou próximo passo de compra.", trace=trace)

    def _buy(
        self,
        package: Mapping[str, Any],
        state: Dict[str, Any],
        event: Mapping[str, Any],
        proposal: Proposal,
        trace: List[Dict[str, Any]],
    ) -> EngineResult:
        offer = self._offer(package, proposal.offer_id or state.get("facts", {}).get("offer_id"))
        if not offer:
            return self._result(event, state, "Qual oferta você quer comprar?", trace=trace)
        pending_type = (state.get("pending") or {}).get("type")
        if pending_type in {"reconcile_checkout", "post_effect_correction"} or (
            state.get("operation") or {}
        ).get("status") == "unknown":
            return self._result(
                event,
                state,
                "Existe uma operação com resultado pendente de conciliação. Não vou iniciar outro checkout antes de resolvê-la.",
                trace=trace + [{"type": "effect_reconciliation_required"}],
            )
        state["facts"]["offer_id"] = offer["id"]
        self.store.cancel_followups(str(package["business"]["id"]), str(state["conversation_id"]))
        if offer.get("kind") == "digital" and not state["facts"].get("quantity"):
            state["facts"]["quantity"] = 1
        state["intent"] = "buy"
        state["phase"] = "ready_to_advance"

        if proposal.requested_action == "charge_customer_with_fabricated_id" or proposal.raw.get("tool") == "charge":
            state["pending"] = {"type": "unsafe_model_action", "reason": "model_cannot_authorize_charge"}
            trace.append({"type": "unsafe_action_rejected", "requested_action": proposal.requested_action})
            return self._result(
                event,
                state,
                "Posso preparar o próximo passo, mas não vou cobrar nem usar um identificador não verificado.",
                trace=trace,
            )

        if package_capability(package, "quote") not in {"enabled", "assisted"}:
            state["pending"] = {"type": "quote_disabled"}
            return self._result(
                event,
                state,
                "A cotação ou proposta ainda não está habilitada para este negócio; vou registrar a solicitação sem inventar condições.",
                trace=trace + [{"type": "capability_blocked", "capability": "quote"}],
            )

        # Conditional purchase is not unconditional permission to close.
        if proposal.condition or state["facts"].get("deadline_condition"):
            delivery = self.commerce.check_delivery(package, offer["id"], state["facts"])
            trace.append({"type": "delivery_checked", "status": delivery.get("status")})
            if delivery.get("status") != "confirmed":
                state["pending"] = {"type": "delivery_confirmation", "condition": state["facts"].get("deadline_condition")}
                return self._result(
                    event,
                    state,
                    "Ainda não consigo confirmar essa condição de prazo. Posso encaminhar para confirmação, sem prometer a entrega.",
                    trace=trace,
                )
            state["facts"]["delivery"] = delivery

        identity_verified = self._identity_verified(event)
        missing = self._missing_for_offer(
            offer,
            state["facts"],
            str(event["contact_id"]),
            identity_verified=identity_verified,
        )
        if missing:
            reason = self._reason_for_field(missing, offer)
            return self._ask(event, state, offer, missing, reason, trace)

        if offer.get("mode") in {"consultative", "proposal", "appointment"} or offer.get("price_type") == "on_request":
            if (state.get("pending") or {}).get("type") == "quote_confirmation" and not state["facts"].get("confirmation"):
                return self._result(event, state, "O escopo está pronto. Confirma que posso preparar a proposta?", trace=trace)
            try:
                result = self.commerce.prepare_proposal(
                    package,
                    offer["id"],
                    state["facts"],
                    business_id=package["business"]["id"],
                    conversation_id=state["conversation_id"],
                )
            except CommerceError as exc:
                trace.append({"type": "proposal_result", "status": exc.status, "code": exc.code})
                if exc.status == "pending" and exc.code == "effect_in_progress":
                    state["operation"] = {
                        "type": "proposal",
                        "status": "pending",
                        "effect_key": exc.details.get("effect_key"),
                        "reservation_id": exc.details.get("reservation_id"),
                    }
                    state["pending"] = {"type": "effect_in_progress", "effect_key": exc.details.get("effect_key")}
                    state["phase"] = "action_in_progress"
                    return self._result(
                        event,
                        state,
                        "Já existe uma proposta em preparação. Não vou duplicá-la; aguarde a confirmação ou peça a conciliação.",
                        trace=trace + [{"type": "proposal_in_progress", "effect_key": exc.details.get("effect_key")}],
                    )
                if exc.status == "unknown":
                    state["operation"] = {
                        "type": "proposal",
                        "status": "unknown",
                        **exc.details,
                    }
                    state["pending"] = {"type": "reconcile_proposal", "effect_key": exc.details.get("effect_key")}
                    state["phase"] = "action_in_progress"
                    return self._result(
                        event,
                        state,
                        "O resultado da proposta não foi confirmado. Não vou repetir a operação; preciso conciliá-la antes de informar um resultado.",
                        trace=trace,
                    )
                return self._result(event, state, "Não consegui preparar a proposta: %s" % str(exc), trace=trace)
            state["operation"] = {"type": "proposal", **result, "status": "confirmed"}
            state["phase"] = "action_in_progress"
            state["pending"] = None
            state.setdefault("memory", {})["open_questions"] = []
            action = {"type": "prepare_proposal", **result}
            return self._result(
                event,
                state,
                "Com os dados disponíveis, preparei a proposta %s. O valor ainda depende da avaliação do escopo." % result["proposal_id"],
                action,
                trace + [{"type": "proposal_prepared"}],
            )

        try:
            new_quote = self.commerce.quote(package, offer["id"], state["facts"], conversation_id=state["conversation_id"])
        except CommerceError as exc:
            state["pending"] = {"type": exc.code}
            return self._result(event, state, str(exc), trace=trace + [{"type": "quote_rejected", "code": exc.code}])

        old_quote = state.get("quote")
        changed = self._quote_changed(old_quote, new_quote)
        state["quote"] = new_quote
        if old_quote and changed and not state["facts"].get("confirmation"):
            state["pending"] = {"type": "quote_confirmation", "quote_id": new_quote["id"]}
            trace.append({"type": "old_quote_invalidated", "old_quote_id": old_quote.get("id")})
            return self._result(
                event,
                state,
                "A quantidade ou o pagamento mudou. A cotação anterior foi invalidada; agora são R$ %.2f. Confirma para eu preparar o checkout?" % new_quote["amount"],
                trace=trace,
            )

        if package_capability(package, "checkout_prepare") not in {"enabled", "assisted"}:
            state["pending"] = {"type": "checkout_disabled"}
            return self._result(event, state, "O checkout ainda não está habilitado para este negócio; vou encaminhar a solicitação.", trace=trace)

        try:
            checkout = self.commerce.prepare_checkout(
                package,
                offer["id"],
                state["facts"],
                new_quote,
                business_id=package["business"]["id"],
                conversation_id=state["conversation_id"],
                contact_id=str(event["contact_id"]),
                identity_verified=identity_verified,
            )
        except CommerceError as exc:
            trace.append({"type": "checkout_result", "status": exc.status, "code": exc.code})
            if exc.status == "pending" and exc.code == "identity_not_verified":
                state["pending"] = {"type": "identity", "reason": "checkout requires verified contact"}
                return self._result(event, state, "Para preparar o checkout, preciso confirmar a identificação do comprador. Qual e-mail devo usar?", trace=trace)
            if exc.status == "pending" and exc.code == "effect_in_progress":
                state["operation"] = {
                    "type": "checkout",
                    "status": "pending",
                    "effect_key": exc.details.get("effect_key"),
                    "reservation_id": exc.details.get("reservation_id"),
                }
                state["pending"] = {"type": "effect_in_progress", "effect_key": exc.details.get("effect_key")}
                state["phase"] = "action_in_progress"
                return self._result(
                    event,
                    state,
                    "Já existe um checkout em preparação. Não vou duplicá-lo; aguarde a confirmação ou peça a conciliação.",
                    trace=trace + [{"type": "checkout_in_progress", "effect_key": exc.details.get("effect_key")}],
                )
            if exc.status == "unknown":
                state["operation"] = {
                    "type": "checkout",
                    "status": "unknown",
                    "quote_id": new_quote["id"],
                    **exc.details,
                }
                state["pending"] = {"type": "reconcile_checkout"}
                return self._result(event, state, "O provedor não confirmou o resultado do checkout. Não vou repetir a operação; preciso conciliá-la antes de informar um link.", trace=trace)
            return self._result(event, state, "Não consegui preparar o checkout: %s" % str(exc), trace=trace)

        state["operation"] = {"type": "checkout", **checkout, "status": "confirmed"}
        state["phase"] = "action_in_progress"
        state["pending"] = None
        state["facts"].pop("confirmation", None)
        state.setdefault("memory", {})["open_questions"] = []
        action = {"type": "prepare_checkout", **checkout}
        response = "O %s custa R$ %.2f. Você pode concluir aqui: %s" % (offer["name"], new_quote["amount"], checkout["url"])
        trace.append({"type": "checkout_prepared", "charged": checkout.get("charged", False)})
        return self._result(event, state, response, action, trace)

    @staticmethod
    def _required_capabilities(result: EngineResult) -> List[str]:
        action = result.action or {}
        action_capabilities = {
            "prepare_checkout": "checkout_prepare",
            "prepare_proposal": "quote",
            "human_transfer": "human_transfer",
        }
        required = []
        if action.get("type") in action_capabilities:
            required.append(action_capabilities[str(action["type"])])
        for item in result.trace:
            if not isinstance(item, Mapping) or item.get("type") != "model_proposal":
                continue
            intent_capabilities = {"price": "catalog_query", "knowledge": "knowledge_query"}
            capability = intent_capabilities.get(str(item.get("intent")))
            if capability and capability not in required:
                required.append(capability)
        return required

    @staticmethod
    def _model_observed_skills(proposal: Proposal) -> Optional[List[Dict[str, Any]]]:
        """Return only an adapter-declared observation, never infer it locally."""

        raw = proposal.raw if isinstance(proposal.raw, Mapping) else {}
        values = raw.get("skills_applied")
        if not isinstance(values, list):
            return None
        observed = []
        for value in values[:32]:
            if isinstance(value, Mapping) and isinstance(value.get("id"), str):
                observed.append({"id": value["id"], "version": value.get("version")})
            elif isinstance(value, str) and value.strip():
                observed.append({"id": value})
        return observed

    @staticmethod
    def _offer(package: Mapping[str, Any], offer_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not offer_id:
            offers = package.get("offers", [])
            return dict(offers[0]) if len(offers) == 1 else None
        for offer in package.get("offers", []):
            if offer.get("id") == offer_id:
                return dict(offer)
        return None

    @staticmethod
    def _merge_safe_facts(
        state: Dict[str, Any],
        proposal: Proposal,
        offer: Optional[Mapping[str, Any]],
        trace: List[Dict[str, Any]],
        *,
        event_id: str = "",
    ) -> None:
        text_fields = {
            "variant",
            "color",
            "payment_method",
            "email",
            "region",
            "company_name",
            "scope",
            "site",
            "deadline_condition",
            "preference",
        }
        changed = {}
        for key, value in proposal.facts.items():
            valid = (
                key in text_fields
                and isinstance(value, str)
                and bool(value.strip())
                and len(value) <= 1000
            ) or (
                key == "quantity"
                and isinstance(value, int)
                and not isinstance(value, bool)
                and 1 <= value <= 1_000_000
            ) or (key == "confirmation" and isinstance(value, bool))
            if not valid:
                trace.append({"type": "fact_rejected", "field": str(key), "reason": "invalid_name_or_value"})
                continue
            if state["facts"].get(key) != value:
                old_value = state["facts"].get(key)
                changed[key] = {"old": old_value, "new": value}
                state["facts"][key] = value
                memory = state.setdefault("memory", {})
                memory.setdefault("fact_history", []).append(
                    {"field": key, "old": old_value, "new": value, "event_id": event_id, "source": "buyer"}
                )
                memory["fact_history"] = memory["fact_history"][-100:]
        if proposal.offer_id and offer:
            if state["facts"].get("offer_id") != offer["id"]:
                changed["offer_id"] = {"old": state["facts"].get("offer_id"), "new": offer["id"]}
            state["facts"]["offer_id"] = offer["id"]
        if changed:
            memory = state.setdefault("memory", {})
            memory["facts"] = dict(state["facts"])
            memory["answered_fields"] = sorted(
                key for key in state["facts"] if not str(key).startswith("_")
            )
            open_questions = [str(item) for item in memory.get("open_questions", [])]
            memory["open_questions"] = [item for item in open_questions if item not in changed]
            trace.append({"type": "facts_updated", "changed": changed})

    @staticmethod
    def _quote_changed(old: Optional[Mapping[str, Any]], new: Mapping[str, Any]) -> bool:
        if not old:
            return False
        fields = ("offer_id", "quantity", "variant", "payment_method", "region", "amount")
        return any(old.get(field) != new.get(field) for field in fields)

    def _identity_verified(self, event: Mapping[str, Any]) -> bool:
        """Accept a channel identity only after its authenticated admission."""

        contact_id = str(event.get("contact_id", ""))
        channel = str(event.get("channel", ""))
        # ``verified:*`` is a synthetic identity reserved for CLI/tests.  It
        # must never authenticate a real-shaped channel event.
        if channel != "chatwoot":
            return contact_id.startswith("verified:")
        if contact_id.startswith("verified:"):
            return False
        context = event.get("channel_context")
        if not isinstance(context, Mapping) or context.get("identity_verified") is not True:
            return False
        return self.store.is_admitted_channel_event(
            "chatwoot",
            context,
            business_id=str(event.get("business_id", "")),
            conversation_id=str(event.get("conversation_id", "")),
            contact_id=contact_id,
        )

    @staticmethod
    def _missing_for_offer(
        offer: Mapping[str, Any],
        facts: Mapping[str, Any],
        contact_id: str,
        *,
        identity_verified: bool = False,
    ) -> Optional[str]:
        for field in offer.get("required_fields", []):
            if not facts.get(field):
                return str(field)
        if (
            offer.get("mode") == "direct"
            and not identity_verified
            and not facts.get("email")
        ):
            return "email"
        return None

    @staticmethod
    def _first_missing(offer: Mapping[str, Any], facts: Mapping[str, Any]) -> str:
        for field in offer.get("required_fields", []):
            if not facts.get(field):
                return str(field)
        return "scope"

    @staticmethod
    def _reason_for_field(field: str, offer: Mapping[str, Any]) -> str:
        reasons = {
            "variant": "o tamanho altera a disponibilidade",
            "quantity": "a quantidade altera a cotação",
            "region": "a região altera a entrega ou o atendimento",
            "email": "o e-mail é necessário para provisionar ou validar o checkout",
            "company_name": "a empresa é necessária para provisionar as licenças",
            "scope": "o escopo muda a recomendação e o orçamento",
        }
        return reasons.get(field, "esse dado é necessário para o próximo passo")

    def _ask(
        self,
        event: Mapping[str, Any],
        state: Dict[str, Any],
        offer: Mapping[str, Any],
        field: str,
        reason: str,
        trace: List[Dict[str, Any]],
    ) -> EngineResult:
        state["pending"] = {"type": "missing_field", "field": field, "reason": reason, "offer_id": offer["id"]}
        state["answered_fields"] = sorted(set(state.get("answered_fields", [])) | set(state["facts"].keys()))
        memory = state.setdefault("memory", {})
        memory["open_questions"] = [field]
        memory["answered_fields"] = list(state["answered_fields"])
        prompts = {
            "variant": "Qual tamanho: %s?" % ", ".join(str(item) for item in offer.get("stock", {}).keys()),
            "quantity": "Quantas unidades você quer?",
            "region": "Para qual região devo verificar a entrega?",
            "email": "Qual e-mail devo usar para preparar o acesso ou checkout?",
            "company_name": "Qual é o nome da empresa para provisionar as licenças?",
            "scope": "Você quer uma reforma completa ou apenas trocar os revestimentos?",
        }
        trace.append({"type": "necessary_question", "field": field, "reason": reason})
        return self._result(event, state, prompts.get(field, "Preciso confirmar %s para continuar." % field), trace=trace)

    @staticmethod
    def _explicit_commercial_resume(text: str, proposal: Proposal, state: Mapping[str, Any]) -> bool:
        """Require a buyer-authored commercial signal to leave a limited profile."""

        value = " ".join(str(text).casefold().split())
        if proposal.intent == "buy":
            return bool(
                re.search(
                    r"\b(?:comprar|compra|contratar|fechar|finalizar|checkout|manda(?:r)? o link|vou levar|quero levar|retomar)\b",
                    value,
                )
                or re.search(r"\bquero\s+(?:o|a|esse|essa)\b", value)
            )
        if proposal.intent == "update":
            # A bare correction is deliberately insufficient. A confirmation
            # can resume only an already established commercial operation.
            has_operation = bool(state.get("quote") or (state.get("operation") or {}).get("type") == "checkout")
            return has_operation and bool(
                re.search(r"\b(?:retomar|continuar|voltar|confirmo|pode seguir|fechar|finalizar)\b", value)
            )
        return False

    @staticmethod
    def _confirmed_effect_conflicts_with_state(effect: Mapping[str, Any], state: Mapping[str, Any]) -> bool:
        """Detect a new buyer fact that no longer describes a confirmed effect."""

        reservation = effect.get("inventory_reservation")
        facts = state.get("facts") if isinstance(state.get("facts"), Mapping) else {}
        if isinstance(reservation, Mapping):
            for fact_name, effect_name in (("offer_id", "offer_id"), ("variant", "variant"), ("quantity", "quantity")):
                fact_value = facts.get(fact_name)
                effect_value = reservation.get(effect_name)
                if fact_value is not None and effect_value is not None and str(fact_value) != str(effect_value):
                    return True
        quote = state.get("quote")
        if isinstance(quote, Mapping) and effect.get("quote_id") and quote.get("id"):
            if str(quote.get("id")) != str(effect.get("quote_id")):
                return True
        return False

    @staticmethod
    def _material_conflict(hits: List[Mapping[str, Any]]) -> bool:
        if not hits:
            return False
        if len(hits) < 2:
            return False
        combined = " ".join(str(hit.get("content", "")) for hit in hits)
        prices = set(re.findall(r"r\$\s*([\d.,]+)", combined, re.I))
        durations = set(re.findall(r"\b(\d+)\s*(?:dias?|meses?|semanas?)\b", combined, re.I))
        revisions = {(str(hit.get("source_id")), str(hit.get("source_version"))) for hit in hits}
        # Keep policy subjects separate. A guarantee, an exchange and a
        # return are different answers even when they occur in the same
        # source. A single document may also state both covered and excluded
        # cases; that is not a source conflict, so only opposite *exclusive*
        # statements across hits count.
        policy_patterns = {
            "guarantee": (
                r"garant(?:ia|ias)",
                r"(?:não|nao)\s+(?:cobre|inclui|abrange|oferece)|sem\s+garantia|(?:não|nao)\s+há\s+garantia",
                r"(?:cobre|inclui|abrange|oferece|vale|válida|valida)",
            ),
            "exchange": (
                r"troca",
                r"(?:não|nao)\s+(?:aceita|permite|cobre).*troca|sem\s+troca",
                r"(?:aceita|permite|cobre).*troca|troca.*(?:aceita|permitida|disponível|disponivel)",
            ),
            "return": (
                r"devoluç(?:ão|ao)|reembolso",
                r"(?:não|nao)\s+(?:aceita|permite|faz|há).*?(?:devoluç(?:ão|ao)|reembolso)|sem\s+(?:devoluç(?:ão|ao)|reembolso)",
                r"(?:aceita|permite|faz|há|disponível|disponivel).*?(?:devoluç(?:ão|ao)|reembolso)|(?:devoluç(?:ão|ao)|reembolso).*?(?:aceita|permitida|disponível|disponivel)",
            ),
            "payment": (
                r"(?:pix|cart(?:ão|ao)|boleto)",
                r"(?:não|nao)\s+(?:aceita|permite|disponibiliza).*?(?:pix|cart(?:ão|ao)|boleto)",
                r"(?:aceita|permite|disponibiliza).*?(?:pix|cart(?:ão|ao)|boleto)",
            ),
            "delivery": (
                r"entrega|envio|entregamos",
                r"(?:não|nao)\s+(?:entrega|enviamos|entregamos)|não\s+há\s+entrega|nao\s+ha\s+entrega",
                r"(?:entrega|envio|entregamos).*?(?:disponível|disponivel|realizado|em\s+\d+)|(?:fazemos|realizamos).*?entrega",
            ),
            "availability": (
                r"estoque|dispon(?:ível|ivel)|disponibilidade",
                r"(?:não|nao)\s+(?:tem|há|ha|está|esta).*?(?:estoque|dispon)|esgotad",
                r"(?:tem|há|ha|está|esta).*?(?:estoque|dispon)|dispon(?:ível|ivel)",
            ),
        }
        semantic_conflict = False
        for keyword, negative_pattern, positive_pattern in policy_patterns.values():
            positive_only = False
            negative_only = False
            for content in (str(hit.get("content", "")) for hit in hits):
                value = content.casefold()
                if not re.search(keyword, value):
                    continue
                negative = bool(re.search(negative_pattern, value))
                # Positive verbs such as "cobre" or "aceita" also occur
                # inside a negated clause ("não cobre"). Do not classify
                # that same hit as a positive-only policy.
                positive = bool(re.search(positive_pattern, value)) and not negative
                positive_only = positive_only or (positive and not negative)
                negative_only = negative_only or (negative and not positive)
            if positive_only and negative_only:
                semantic_conflict = True
                break
        return bool(
            semantic_conflict
            or (len(revisions) > 1 and (len(prices) > 1 or len(durations) > 1))
        )

    @staticmethod
    def _evidence_answer(question: str, content: str) -> str:
        if "acesso" in question.casefold() or "acesso" in content.casefold():
            return content
        return content

    @staticmethod
    def _topic_label(topic: str) -> str:
        return {
            "guarantee": "a garantia",
            "exchange": "a política de troca",
            "return": "a política de devolução",
            "price": "o preço",
            "access": "o acesso",
            "delivery": "a entrega",
            "payment": "o pagamento",
            "availability": "a disponibilidade",
            "general": "essa condição",
        }.get(topic, topic)

    @staticmethod
    def _evidence_covers_topic(topic: str, evidence: Mapping[str, Any]) -> bool:
        content = str(evidence.get("content", "")).casefold()
        terms = {
            "guarantee": ("garantia",),
            "exchange": ("troca",),
            "return": ("devolu", "reembolso"),
            "access": ("acesso", "libera", "dura", "meses"),
            "delivery": ("entrega", "prazo", "envio", "chegar"),
            "payment": ("pagamento", "pix", "cartao", "cartão", "parcel"),
            "availability": ("estoque", "dispon", "tamanho", "unidade"),
            "price": ("preço", "preco", "custa", "valor", "r$"),
            "general": ("",),
        }.get(topic, (topic,))
        return any(term in content for term in terms)

    def _maybe_draft(self, package: Mapping[str, Any], event: Mapping[str, Any], result: EngineResult) -> None:
        if package.get("draft_mode", "off") != "on" or not result.response:
            return
        if result.state.get("status") == "human_paused" or any(
            item.get("type") in {"model_contract_failed", "model_error", "channel_event_rejected"}
            for item in result.trace
        ):
            return
        draft_response = getattr(self.model, "draft_response", None)
        if not callable(draft_response):
            result.trace.append({"type": "draft_fallback", "reason": "drafter_unavailable"})
            return
        trusted_evidence = []
        for item in result.evidence:
            if not isinstance(item, Mapping):
                continue
            if not item.get("source_id") or not item.get("source_version"):
                continue
            source = next((row for row in self.store.list_sources(str(package["business"]["id"]))
                           if row.get("source_id") == item.get("source_id")
                           and row.get("source_version") == item.get("source_version")
                           and row.get("status") == "approved" and row.get("review_status") == "approved"
                           and row.get("active")
                           and (not row.get("valid_from") or datetime.fromisoformat(str(row["valid_from"]).replace("Z", "+00:00"))
                                <= datetime.fromisoformat(self.store.clock.now().replace("Z", "+00:00")))
                           and (not row.get("valid_until") or datetime.fromisoformat(str(row["valid_until"]).replace("Z", "+00:00"))
                                >= datetime.fromisoformat(self.store.clock.now().replace("Z", "+00:00")))), None)
            if source is not None and all(
                key not in item or str(item.get(key) or "") == str(source.get(key) or "")
                for key in ("scope", "audience", "subject", "generation")
            ):
                trusted_evidence.append(dict(item))
        requirements = ResponseRequirements.from_result(
            str(event.get("text", "")), EngineResult(result.event_id, result.conversation_id, result.response,
                                                      action=result.action, state=result.state, evidence=trusted_evidence),
        )
        feedback: list[dict[str, str]] = []
        for attempt in range(2):
            try:
                draft = draft_response(requirements, feedback)
            except Exception:
                result.trace.append({"type": "draft_fallback", "reason": "drafter_error"})
                return
            if not isinstance(draft, str) or not draft.strip() or len(draft) > MAX_EVENT_TEXT_LENGTH:
                feedback = [{"kind": "invalid_draft", "value": "empty_or_too_long"}]
            else:
                feedback = ClaimVerifier.verify(draft, requirements)
            if not feedback:
                result.response = draft.strip()
                result.trace.append({"type": "draft_accepted", "attempt": attempt + 1})
                return
            result.trace.append({"type": "claim_unsupported", "attempt": attempt + 1, "claims": feedback})
        result.trace.append({"type": "draft_fallback", "reason": "verification_failed"})

    def _service_hours_message(self, package: Mapping[str, Any]) -> str:
        hours = package.get("service_hours")
        if not isinstance(hours, Mapping):
            return " Disponibilidade do atendimento humano não informada."
        now = datetime.fromisoformat(self.store.clock.now().replace("Z", "+00:00")).astimezone(
            ZoneInfo(str(hours["timezone"]))
        )
        intervals = hours["intervals"]
        for days_ahead in range(8):
            day = now + timedelta(days=days_ahead)
            for interval in intervals.get(day.strftime("%A").lower(), []):
                start_hour, start_minute = map(int, interval["start"].split(":"))
                end_hour, end_minute = map(int, interval["end"].split(":"))
                opening = day.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                closing = day.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
                if opening <= now < closing:
                    return " O atendimento humano está dentro do horário informado."
                if opening > now:
                    when = "amanhã" if days_ahead == 1 else "hoje" if days_ahead == 0 else day.strftime("%A")
                    time_label = f"{start_hour}h" + (f"{start_minute:02d}" if start_minute else "")
                    return f" O próximo horário de atendimento é {when} às {time_label}."
        return " Disponibilidade do atendimento humano não informada."

    @staticmethod
    def _result(
        event: Mapping[str, Any],
        state: Dict[str, Any],
        response: str,
        action: Optional[Dict[str, Any]] = None,
        trace: Optional[List[Dict[str, Any]]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> EngineResult:
        return EngineResult(
            event_id=str(event["event_id"]),
            conversation_id=str(event["conversation_id"]),
            response=response,
            action=action,
            state=state,
            evidence=evidence or [],
            trace=trace or [],
        )
