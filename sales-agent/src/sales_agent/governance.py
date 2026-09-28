"""Local controls for gradual activation and quality supervision.

These controls are deliberately persistent and structured.  A prompt or skill
can suggest content, but it cannot enable a pilot, change a cohort, or grant a
supervisor permission to send.
"""

from __future__ import annotations

import math
import re
import tempfile
import threading
import time
import uuid
from queue import Empty, Queue
from typing import Any, Callable, Dict, Mapping, Optional

from .drafting import commercial_claims, policy_claims
from .storage import StateStore, durable_key, normalize_iso_datetime, utc_now
from .validation import package_capability, package_fingerprint

MODES = {"observation", "assistance", "pilot"}

DEFAULT_OPERATOR_PLAN = {
    "validation": {
        "required": [
            "evaluated_package_version",
            "cohort",
            "limits",
            "backend_and_model_evidence",
        ],
        "external_execution": "not-executed-until-provider-is-configured",
    },
    "reversal": {
        "command": "pilot interrupt",
        "scope": "business-and-channel",
        "effect": "block-new-deliveries-and-revalidate-claimed-items",
    },
    "retention": {
        "metrics": "structured-counters",
        "raw_buyer_text": "not-copied-to-pilot-metrics",
        "period": "operator-defined-before-activation",
    },
}


def scope_key(business_id: str, channel: str) -> str:
    return "%s:%s" % (business_id, channel)


class PilotController:
    """Persisted observation/assistance/pilot decision point."""

    def __init__(self, store: StateStore):
        self.store = store

    def configure(
        self,
        business_id: str,
        channel: str,
        *,
        mode: str = "observation",
        cohort: Optional[Mapping[str, Any]] = None,
        limits: Optional[Mapping[str, Any]] = None,
        evaluated_package_version: Optional[str] = None,
        evaluated_package_fingerprint: Optional[str] = None,
        evaluated_model: Optional[str] = None,
        evaluated_backend: Optional[str] = None,
        evaluation_evidence: Optional[Mapping[str, Any]] = None,
        authorize: bool = False,
        reason: str = "",
    ) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError("modo deve ser observation, assistance ou pilot")
        package = self.store.get_business(business_id)
        if not package:
            raise ValueError("negócio não configurado: %s" % business_id)
        current_package_fingerprint = package_fingerprint(package)
        if mode == "pilot":
            if not authorize:
                raise ValueError("piloto exige autorização explícita")
            if not evaluated_package_version or evaluated_package_version != package.get("package_version"):
                raise ValueError("piloto exige versão do pacote avaliada e vigente")
            if not cohort:
                raise ValueError("piloto exige coorte explícita")
            normalized_limits = dict(limits or {})
            recognized_limits = {"max_events", "max_deliveries", "max_cost", "max_latency_ms", "expires_at", "until"}
            unknown_limits = sorted(set(normalized_limits) - recognized_limits)
            if unknown_limits:
                raise ValueError("limite de piloto desconhecido: %s" % ", ".join(unknown_limits))
            if not self._valid_cohort(cohort):
                raise ValueError("piloto exige coorte estruturada reconhecida")
            for name in ("max_events", "max_deliveries", "max_cost", "max_latency_ms"):
                if name in normalized_limits:
                    value = normalized_limits[name]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                        or value <= 0
                    ):
                        raise ValueError("limite de piloto inválido: %s" % name)
            if not normalized_limits:
                raise ValueError("piloto exige limites explícitos")
            for name in ("expires_at", "until"):
                if name in normalized_limits:
                    value = normalized_limits[name]
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError("período de piloto inválido")
                    try:
                        normalized_limits[name] = normalize_iso_datetime(value)
                    except ValueError as exc:
                        raise ValueError("período de piloto inválido") from exc
            evidence = dict(evaluation_evidence or self._local_evaluation_evidence(package))
            if not self._evaluation_matches(
                evidence,
                package,
                evaluated_model,
                evaluated_backend,
                evaluated_package_fingerprint,
            ):
                raise ValueError("piloto exige evidência de avaliação aprovada para pacote, modelo e backend")
            evaluated_package_fingerprint = evaluated_package_fingerprint or str(
                evidence.get("candidate_package_fingerprint")
                or (
                    evidence.get("evaluation", {}).get("candidate", {})
                    if isinstance(evidence.get("evaluation"), Mapping)
                    else {}
                ).get("package_fingerprint")
                or current_package_fingerprint
            )
            if evaluated_package_fingerprint != current_package_fingerprint:
                raise ValueError("piloto exige fingerprint do pacote avaliado e vigente")
            evaluated_model = evaluated_model or str(evidence.get("model", {}).get("name", ""))
            evaluated_backend = evaluated_backend or str(evidence.get("backend", {}).get("name", ""))
        value = self.store.save_operating_mode(
            scope_key(business_id, channel),
            business_id,
            channel,
            mode,
            enabled=True,
            cohort=cohort,
            limits=normalized_limits if mode == "pilot" else limits,
            evaluated_package_version=evaluated_package_version,
            evaluated_package_fingerprint=evaluated_package_fingerprint,
            evaluated_model=evaluated_model,
            evaluated_backend=evaluated_backend,
            reason=reason or ("authorized by owner" if authorize else "local configuration"),
        )
        self.store.update_pilot_metrics(value["scope_key"], {"configuration_changes": 1})
        return self.public_config(value)

    @staticmethod
    def _valid_cohort(cohort: Mapping[str, Any]) -> bool:
        if not isinstance(cohort, Mapping) or not cohort:
            return False
        if cohort.get("all") is True:
            return True
        for key in ("contacts", "conversations", "contact_prefixes"):
            value = cohort.get(key)
            if isinstance(value, list) and value and all(isinstance(item, (str, int)) and str(item).strip() for item in value):
                return True
        return False

    @staticmethod
    def _evaluation_matches(
        evidence: Mapping[str, Any],
        package: Mapping[str, Any],
        evaluated_model: Optional[str],
        evaluated_backend: Optional[str],
        evaluated_package_fingerprint: Optional[str] = None,
    ) -> bool:
        evaluation = evidence.get("evaluation") if isinstance(evidence.get("evaluation"), Mapping) else {}
        model = evidence.get("model") if isinstance(evidence.get("model"), Mapping) else {}
        backend = evidence.get("backend") if isinstance(evidence.get("backend"), Mapping) else {}
        package_version = evidence.get("candidate_package_version") or evidence.get("package_version")
        candidate_fingerprint = evidence.get("candidate_package_fingerprint")
        if not candidate_fingerprint and isinstance(evidence.get("evaluation"), Mapping):
            candidate = evidence["evaluation"].get("candidate")
            if isinstance(candidate, Mapping):
                candidate_fingerprint = candidate.get("package_fingerprint")
        fingerprint_matches = (
            str(candidate_fingerprint) == package_fingerprint(package)
            if candidate_fingerprint
            else evaluated_package_fingerprint is None
        )
        # Reports generated by this version always carry a fingerprint.  Keep
        # accepting the older structured evidence shape for local operators,
        # but only when no fingerprint was supplied that could contradict the
        # package currently being activated.  A supplied stale fingerprint is
        # never ignored.
        return bool(
            evidence.get("status") == "passed"
            and evaluation.get("thresholds_met") is True
            and str(package_version) == str(package.get("package_version"))
            and fingerprint_matches
            and (not evaluated_package_fingerprint or str(evaluated_package_fingerprint) == str(candidate_fingerprint))
            and (not evaluated_model or str(evaluated_model) == str(model.get("name")))
            and (not evaluated_backend or str(evaluated_backend) == str(backend.get("name")))
        )

    @staticmethod
    def _local_evaluation_evidence(package: Mapping[str, Any]) -> Dict[str, Any]:
        from .evaluation import EvaluationRunner

        with tempfile.TemporaryDirectory(prefix="vendedor-pilot-eval-") as temporary:
            report = EvaluationRunner(
                temporary,
                candidate_package=package,
                candidate_business_id=str(package.get("business", {}).get("id", "")),
            ).run()
        report["candidate_package_version"] = package.get("package_version")
        report["candidate_package_fingerprint"] = package_fingerprint(package)
        return report

    def interrupt(self, business_id: str, channel: str, *, reason: str = "interrompido pelo operador") -> Dict[str, Any]:
        current = self.store.get_operating_mode(scope_key(business_id, channel))
        if not current:
            current = self.store.save_operating_mode(
                scope_key(business_id, channel), business_id, channel, "observation", reason=reason
            )
        else:
            current = self.store.save_operating_mode(
                scope_key(business_id, channel),
                business_id,
                channel,
                str(current["mode"]),
                enabled=False,
                cohort=current.get("cohort"),
                limits=current.get("limits"),
                evaluated_package_version=current.get("evaluated_package_version"),
                evaluated_package_fingerprint=current.get("evaluated_package_fingerprint"),
                evaluated_model=current.get("evaluated_model"),
                evaluated_backend=current.get("evaluated_backend"),
                reason=reason,
            )
        self.store.update_pilot_metrics(current["scope_key"], {"interruptions": 1})
        return self.public_config(current)

    def inspect(self, business_id: str, channel: str) -> Dict[str, Any]:
        key = scope_key(business_id, channel)
        config = self.store.get_operating_mode(key)
        if not config:
            config = {
                "scope_key": key,
                "business_id": business_id,
                "channel": channel,
                "mode": "observation",
                "enabled": True,
                "cohort": {},
                "limits": {},
                "evaluated_package_version": None,
                "evaluated_package_fingerprint": None,
                "evaluated_model": None,
                "evaluated_backend": None,
                "reason": "default safe observation",
                "updated_at": None,
            }
        return {
            "config": self.public_config(config),
            "metrics": self.store.get_pilot_metrics(key),
            "operator_plan": {
                "validation": dict(DEFAULT_OPERATOR_PLAN["validation"]),
                "reversal": dict(DEFAULT_OPERATOR_PLAN["reversal"]),
                "retention": dict(DEFAULT_OPERATOR_PLAN["retention"]),
            },
        }

    def _decide(self, item: Mapping[str, Any], *, reserve: bool) -> Dict[str, Any]:
        business_id = str(item.get("business_id", ""))
        channel = str(item.get("channel", "cli"))
        action = item.get("action") if isinstance(item.get("action"), Mapping) else {}
        window_notice = (
            channel == "chatwoot"
            and str(item.get("message_key", "")).startswith("window-note:")
            and action.get("type") == "private_note"
        )
        config = self.store.get_operating_mode(scope_key(business_id, channel))
        if config is None:
            if window_notice and self.store.get_business(business_id):
                return {"send": True, "mode": "observation", "reason": "internal_window_notice"}
            # The safe default is observation. It is returned as a decision so
            # the worker can audit why no public message was sent.
            return {"send": False, "mode": "observation", "reason": "default_observation", "scope_key": scope_key(business_id, channel)}
        if not config.get("enabled"):
            return {"send": False, "mode": config["mode"], "reason": "interrupted", "scope_key": config["scope_key"]}
        package = self.store.get_business(business_id)
        if not package:
            return {"send": False, "mode": config["mode"], "reason": "business_missing", "scope_key": config["scope_key"]}
        if window_notice:
            return {"send": True, "mode": config["mode"], "reason": "internal_window_notice"}
        if config["mode"] == "pilot" and (
            config.get("evaluated_package_version") != package.get("package_version")
            or config.get("evaluated_package_fingerprint") != package_fingerprint(package)
        ):
            return {"send": False, "mode": "pilot", "reason": "package_changed_since_evaluation", "scope_key": config["scope_key"]}
        if not self._in_cohort(item, config.get("cohort") or {}):
            return {"send": False, "mode": config["mode"], "reason": "outside_cohort", "scope_key": config["scope_key"]}
        metrics = self.store.get_pilot_metrics(config["scope_key"])
        limits = config.get("limits") or {}
        expires_at = limits.get("expires_at") or limits.get("until")
        if config["mode"] == "pilot" and expires_at and str(utc_now()) >= str(expires_at):
            return {"send": False, "mode": "pilot", "reason": "pilot_period_expired", "scope_key": config["scope_key"]}
        estimated_cost = self._metric_value(item, "cost", 0)
        item_latency = self._metric_value(item, "latency_ms", None)
        if config["mode"] == "pilot" and limits.get("max_latency_ms") is not None and isinstance(item_latency, (int, float)) and item_latency > float(limits["max_latency_ms"]):
            return {"send": False, "mode": "pilot", "reason": "latency_limit", "scope_key": config["scope_key"]}
        reservation_key = str(
            item.get("message_key")
            or durable_key("pilot-item", business_id, str(item.get("conversation_id", "")), str(item.get("event_id", "")))
        )
        if config["mode"] == "pilot" and reserve:
            try:
                estimated_cost = float(estimated_cost)
            except (TypeError, ValueError):
                estimated_cost = 0.0
            slot = self.store.try_consume_pilot_limits(
                config["scope_key"], limits, estimated_cost=estimated_cost, reservation_key=reservation_key
            )
            if not slot.get("allowed"):
                return {"send": False, "mode": "pilot", "reason": slot.get("reason"), "scope_key": config["scope_key"]}
            metrics = slot.get("counters", metrics)
        if config["mode"] in {"observation", "assistance"}:
            return {"send": False, "mode": config["mode"], "reason": "mode_does_not_send_publicly", "scope_key": config["scope_key"]}
        return {
            "send": True,
            "mode": "pilot",
            "reason": "pilot_limit_allows",
            "scope_key": config["scope_key"],
            "estimated_cost": estimated_cost,
            "_slot_reserved": bool(config["mode"] == "pilot" and reserve),
            "_reservation_key": reservation_key,
        }

    def decide(self, item: Mapping[str, Any]) -> Dict[str, Any]:
        return self._decide(item, reserve=True)

    def record(
        self,
        item: Mapping[str, Any],
        result: Mapping[str, Any],
        *,
        decision: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, int]:
        """Record an outcome without re-running the admission decision.

        A second limit check here would race with other workers and could
        consume a fresh event slot while recording an item that was already
        observed or cancelled.  The decision returned by ``decide`` carries
        the reservation ownership for this outcome.
        """

        key = scope_key(str(item.get("business_id", "")), str(item.get("channel", "cli")))
        config = self.store.get_operating_mode(key)
        pilot_mode = bool(config and config.get("mode") == "pilot")
        increments: Dict[str, Any] = {}
        if not pilot_mode:
            increments["events"] = 1
        status = str(result.get("status", ""))
        reservation_key = str(
            (decision or {}).get("_reservation_key")
            or item.get("message_key")
            or durable_key("pilot-item", str(item.get("business_id", "")), str(item.get("conversation_id", "")), str(item.get("event_id", "")))
        )
        settled = False
        settlement_reason = ""
        if pilot_mode:
            cost_value = self._metric_value(result, "cost", None)
            settled_result = self.store.settle_pilot_reservation(
                key,
                reservation_key,
                status,
                actual_cost=cost_value if isinstance(cost_value, (int, float)) and not isinstance(cost_value, bool) else None,
            )
            settled = bool(settled_result.get("settled"))
            settlement_reason = str(settled_result.get("reason", ""))
        if not pilot_mode and status in {"sent", "confirmed", "accepted"}:
            increments["deliveries"] = 1
        if status == "cancelled" and (not pilot_mode or settled or settlement_reason == "reservation_not_found"):
            increments["cancellations"] = 1
        if status in {"unknown", "dead_letter"} and (not pilot_mode or settled):
            increments["failures"] = 1
        action = item.get("action")
        if (
            isinstance(action, Mapping)
            and action.get("type") == "human_transfer"
            and status in {"sent", "confirmed", "accepted"}
        ):
            increments["handoff"] = 1
        if result.get("reason") == "evidence_invalidated":
            increments["missing_evidence"] = 1
        latency = self._metric_value(result, "latency_ms", None)
        cost_value = self._metric_value(result, "cost", None)
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            increments["latency_ms"] = float(latency)
        if isinstance(cost_value, (int, float)) and not isinstance(cost_value, bool) and not settled:
            increments["cost"] = float(cost_value)
        return self.store.update_pilot_metrics(key, increments)

    @staticmethod
    def _metric_value(value: Any, name: str, default: Any) -> Any:
        """Read provider metrics without treating an explicit null as final."""

        if not isinstance(value, Mapping):
            return default
        direct = value.get(name)
        if direct is not None:
            return direct
        for child in value.values():
            if isinstance(child, Mapping):
                found = PilotController._metric_value(child, name, None)
                if found is not None:
                    return found
        return default

    def record_inbound(self, item: Mapping[str, Any], *, accepted: bool, reason: str = "") -> Dict[str, int]:
        key = scope_key(str(item.get("business_id", "")), str(item.get("channel", "cli")))
        increments = {"received": 1, "queued": 1 if accepted else 0, "ignored": 0 if accepted else 1}
        if reason in {"private_message", "self_authored", "outgoing"}:
            increments["self_or_private_events"] = 1
        return self.store.update_pilot_metrics(key, increments)

    @staticmethod
    def _in_cohort(item: Mapping[str, Any], cohort: Mapping[str, Any]) -> bool:
        if not cohort:
            return False
        contact_id = str(item.get("contact_id", ""))
        conversation_id = str(item.get("conversation_id", ""))
        contacts = cohort.get("contacts")
        conversations = cohort.get("conversations")
        prefixes = cohort.get("contact_prefixes")
        if isinstance(contacts, list) and contacts:
            return contact_id in {str(value) for value in contacts}
        if isinstance(conversations, list) and conversations:
            return conversation_id in {str(value) for value in conversations}
        if isinstance(prefixes, list) and prefixes:
            return any(contact_id.startswith(str(value)) for value in prefixes)
        return bool(cohort.get("all"))

    @staticmethod
    def public_config(value: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "scope_key": value.get("scope_key"),
            "business_id": value.get("business_id"),
            "channel": value.get("channel"),
            "mode": value.get("mode"),
            "enabled": bool(value.get("enabled")),
            "cohort": dict(value.get("cohort") or {}),
            "limits": dict(value.get("limits") or {}),
            "evaluated_package_version": value.get("evaluated_package_version"),
            "evaluated_package_fingerprint": value.get("evaluated_package_fingerprint"),
            "evaluated_model": value.get("evaluated_model"),
            "evaluated_backend": value.get("evaluated_backend"),
            "reason": value.get("reason"),
            "updated_at": value.get("updated_at"),
        }


class QualitySupervisor:
    """Observe candidate quality and optionally apply one bounded correction."""

    def __init__(
        self,
        store: StateStore,
        *,
        mode: str = "off",
        policy: str = "optional",
        reviewer: Optional[Callable[[Mapping[str, Any]], Mapping[str, Any]]] = None,
        timeout_seconds: float = 2.0,
        scope_key: str = "global",
    ):
        persisted = store.get_supervisor_setting(scope_key)
        if persisted is not None and mode == "off":
            mode = str(persisted["mode"])
            policy = str(persisted.get("policy", policy))
        if mode not in {"off", "observation", "selective"}:
            raise ValueError("modo de supervisor inválido")
        if policy not in {"optional", "mandatory"}:
            raise ValueError("política de supervisor inválida")
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("timeout do supervisor inválido")
        self.store = store
        self.mode = mode
        self.policy = policy
        self.scope_key = scope_key
        self.reviewer = reviewer
        self.timeout_seconds = timeout_seconds
        self._corrections: Dict[str, int] = {}

    def configure(self, mode: str, *, policy: Optional[str] = None) -> Dict[str, Any]:
        if mode not in {"off", "observation", "selective"}:
            raise ValueError("modo de supervisor inválido")
        if policy is not None and policy not in {"optional", "mandatory"}:
            raise ValueError("política de supervisor inválida")
        self.mode = mode
        if policy is not None:
            self.policy = policy
        setting = self.store.save_supervisor_setting(self.scope_key, mode, policy=self.policy, correction_limit=1)
        return {
            "mode": mode,
            "policy": self.policy,
            "enabled": mode != "off",
            "correction_limit": setting["correction_limit"],
        }

    def report(self, candidate_id: Optional[str] = None) -> Dict[str, Any]:
        """Return aggregate supervisor evidence without exposing conversation text."""

        all_reviews = self.store.list_supervisor_reviews()
        if candidate_id is None:
            reviews = all_reviews
        else:
            requested_candidate = str(candidate_id)
            reviews = [
                item
                for item in all_reviews
                if self._candidate_root(item) == requested_candidate
            ]
        primary_reviews = self._primary_reviews(reviews)
        issues: Dict[str, int] = {}
        latency_ms = 0.0
        cost = 0.0
        reviewer_completed = 0
        reviewer_rejections = 0
        reviewer_errors = 0
        reviewer_timeouts = 0
        false_positives = 0
        corrections = 0
        corrections_blocked = 0
        deterministic_failures = 0
        quality_dimension_failures: Dict[str, int] = {}
        package_versions = set()
        package_fingerprints = set()
        for review in reviews:
            status = str(review.get("status", ""))
            if status == "corrected":
                corrections += 1
            if status in {"correction_blocked", "blocked"}:
                corrections_blocked += 1
        for review in primary_reviews:
            package_version = review.get("package_version")
            if package_version is not None:
                package_versions.add(str(package_version))
            package_fingerprint_value = review.get("package_fingerprint")
            if package_fingerprint_value is not None:
                package_fingerprints.add(str(package_fingerprint_value))
            if self._has_deterministic_failure(review):
                deterministic_failures += 1
            dimensions = review.get("quality_dimensions", {})
            if isinstance(dimensions, Mapping):
                for name, value in dimensions.items():
                    if value is False:
                        quality_dimension_failures[str(name)] = quality_dimension_failures.get(str(name), 0) + 1
            reviewer = review.get("reviewer", {})
            if not isinstance(reviewer, Mapping):
                continue
            if isinstance(reviewer.get("latency_ms"), (int, float)):
                latency_ms += float(reviewer["latency_ms"])
            if reviewer.get("timed_out"):
                reviewer_timeouts += 1
            reviewer_status = str(reviewer.get("status", ""))
            if reviewer_status == "completed":
                reviewer_completed += 1
            elif reviewer_status == "error":
                reviewer_errors += 1
            result = reviewer.get("result", {})
            if not isinstance(result, Mapping):
                continue
            if result.get("status") == "rejected":
                reviewer_rejections += 1
            if result.get("false_positive"):
                false_positives += 1
            if isinstance(result.get("cost"), (int, float)) and not isinstance(result.get("cost"), bool):
                cost += float(result["cost"])
            for issue in result.get("issues", []):
                if isinstance(issue, str) and issue:
                    issues[issue] = issues.get(issue, 0) + 1
        return {
            "mode": self.mode,
            "scope_key": self.scope_key,
            "candidate_id": candidate_id,
            "package_versions": sorted(package_versions),
            "package_fingerprints": sorted(package_fingerprints),
            "summary": {
                "reviews": len(primary_reviews),
                "reviewer_completed": reviewer_completed,
                "reviewer_rejections": reviewer_rejections,
                "reviewer_errors": reviewer_errors,
                "reviewer_timeouts": reviewer_timeouts,
                "false_positives": false_positives,
                "corrections": corrections,
                "corrections_blocked": corrections_blocked,
                "deterministic_failures": deterministic_failures,
                "latency_ms": round(latency_ms, 3),
                "cost": int(cost) if cost.is_integer() else round(cost, 6),
                "issues": dict(sorted(issues.items())),
                "quality_dimension_failures": dict(sorted(quality_dimension_failures.items())),
            },
            "comparison": self._comparison(reviews, cost=cost, latency_ms=latency_ms, deterministic_failures=deterministic_failures),
            "policy": self.policy,
            "disable": {"mode": "off", "requires_conversation_migration": False},
            "evidence_class": "local-supervisor-observation",
        }

    @staticmethod
    def _candidate_root(review: Mapping[str, Any]) -> str:
        """Return the original candidate id for any review audit row."""

        for key in ("parent_candidate_id", "original_candidate_id", "candidate_id"):
            value = review.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return ""

    @classmethod
    def _primary_reviews(cls, reviews: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Select one original observation per candidate.

        Correction and blocked-correction rows are audit outcomes, not new
        candidates.  Older rows may not carry ``parent_candidate_id`` yet, so
        their status is also used to keep them out of the denominator.
        """

        derived_statuses = {"corrected", "correction_blocked", "blocked"}
        selected: Dict[str, Mapping[str, Any]] = {}
        for review in reviews:
            if review.get("parent_candidate_id") or review.get("original_candidate_id") not in {None, review.get("candidate_id")}:
                continue
            if str(review.get("status", "")) in derived_statuses:
                continue
            root = cls._candidate_root(review)
            if root and root not in selected:
                selected[root] = review
        return list(selected.values())

    @staticmethod
    def _has_deterministic_failure(review: Mapping[str, Any]) -> bool:
        checks = review.get("deterministic", {})
        return isinstance(checks, Mapping) and any(value is False for value in checks.values())

    @staticmethod
    def _has_quality_dimension_failure(review: Mapping[str, Any]) -> bool:
        dimensions = review.get("quality_dimensions", {})
        return isinstance(dimensions, Mapping) and any(value is False for value in dimensions.values())

    def observe(
        self,
        event: Mapping[str, Any],
        result: Mapping[str, Any],
        package: Mapping[str, Any],
        *,
        candidate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        candidate = candidate_id or durable_key(
            "candidate", str(event.get("business_id", "")), str(event.get("conversation_id", "")), str(event.get("event_id", ""))
        )
        base = {
            "candidate_id": candidate,
            "original_candidate_id": candidate,
            "business_id": str(event.get("business_id", "")),
            "conversation_id": str(event.get("conversation_id", "")),
            "event_id": str(event.get("event_id", "")),
            "package_version": package.get("package_version"),
            "package_fingerprint": package_fingerprint(package),
            "state_version": (result.get("state") or {}).get("version"),
            "state_version_before": max(0, int((result.get("state") or {}).get("version", 0)) - 1),
            "mode": self.mode,
            "status": "disabled" if self.mode == "off" else "observed",
            "evidence_ids": [str(item.get("evidence_id")) for item in result.get("evidence", []) if isinstance(item, Mapping)],
            "deterministic": self._deterministic_checks(result),
            "quality_dimensions": self._quality_dimensions(result),
            "baseline": {"cost": 0, "latency_ms": 0},
            "reviewer": {"status": "not-run"},
        }
        if self.mode != "off" and self.reviewer is not None:
            started = time.perf_counter()
            review_queue: Queue = Queue(maxsize=1)

            def run_reviewer() -> None:
                try:
                    review_queue.put(("completed", dict(self.reviewer(self._review_input(event, result, package)))))
                except Exception as exc:  # reviewer is an untrusted boundary
                    review_queue.put(("error", exc))

            reviewer_thread = threading.Thread(
                target=run_reviewer, name="seller-supervisor", daemon=True
            )
            reviewer_thread.start()
            reviewer_thread.join(timeout=self.timeout_seconds)
            if reviewer_thread.is_alive():
                base["reviewer"] = {
                    "status": "timeout",
                    "timed_out": True,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            else:
                try:
                    reviewer_status, reviewer_value = review_queue.get_nowait()
                except Empty:
                    reviewer_status, reviewer_value = "error", RuntimeError("revisor não retornou resultado")
                if reviewer_status == "completed":
                    review = reviewer_value
                    elapsed = (time.perf_counter() - started) * 1000
                    base["reviewer"] = {"status": "completed", "result": self._public_review(review), "latency_ms": round(elapsed, 3)}
                    base["reviewer"]["timed_out"] = False
                else:
                    exc = reviewer_value
                    base["reviewer"] = {"status": "error", "error": str(exc)[:300], "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
        if self.mode == "selective":
            base["status"] = "selective_candidate"
        review_id = durable_key("supervisor-review", candidate, str(uuid.uuid4()))
        saved = self.store.save_supervisor_review({**base, "review_id": review_id})
        return saved

    def apply_selective(
        self,
        event: Mapping[str, Any],
        result: Mapping[str, Any],
        package: Mapping[str, Any],
        review: Mapping[str, Any],
        correction: Mapping[str, Any],
    ) -> Dict[str, Any]:
        candidate = str(review.get("candidate_id", ""))
        if self.mode != "selective":
            return {"applied": False, "reason": "selective_mode_disabled", "result": dict(result)}
        correction_audits = {"corrected", "correction_blocked", "blocked"}
        if self._corrections.get(candidate, 0) >= 1 or any(
            item.get("status") in correction_audits
            and (
                item.get("parent_candidate_id") == candidate
                or item.get("original_candidate_id") == candidate
                or item.get("candidate_id") == candidate
            )
            for item in self.store.list_supervisor_reviews()
        ):
            return {"applied": False, "reason": "correction_limit", "result": dict(result)}
        expected_candidate = durable_key(
            "candidate", str(event.get("business_id", "")), str(event.get("conversation_id", "")), str(event.get("event_id", ""))
        )
        if candidate != expected_candidate or (result.get("candidate_id") and str(result.get("candidate_id")) != candidate):
            return {"applied": False, "reason": "candidate_changed", "result": dict(result)}
        if (
            candidate != str(review.get("candidate_id", ""))
            or review.get("package_version") != package.get("package_version")
            or review.get("package_fingerprint") != package_fingerprint(package)
        ):
            return {"applied": False, "reason": "candidate_or_package_changed", "result": dict(result)}
        current_package = self.store.get_business(str(event.get("business_id", "")))
        if not current_package or current_package.get("package_version") != package.get("package_version"):
            return {"applied": False, "reason": "package_changed_since_review", "result": dict(result)}
        if package_fingerprint(current_package) != str(review.get("package_fingerprint")):
            return {"applied": False, "reason": "package_changed_since_review", "result": dict(result)}
        candidate_state = result.get("state") if isinstance(result.get("state"), Mapping) else {}
        contact_id = str(candidate_state.get("contact_id") or event.get("contact_id") or "unknown")
        current_state = self.store.load_conversation(
            str(event.get("business_id", "")), str(event.get("conversation_id", "")), contact_id
        )
        reviewed_before = review.get("state_version_before")
        candidate_version = candidate_state.get("version")
        if reviewed_before is not None and int(current_state.get("version", 0)) != int(reviewed_before):
            # A candidate is reviewed before SellerEngine commits its own
            # event.  Any durable advance since that snapshot invalidates the
            # correction; a pre-committed direct caller may still be accepted
            # only when its control state is identical.
            if not (
                candidate_version is not None
                and int(current_state.get("version", 0)) == int(candidate_version)
                and self._state_control_snapshot(current_state) == self._state_control_snapshot(candidate_state)
            ):
                return {"applied": False, "reason": "state_changed_since_review", "result": dict(result)}
        for capability in self._required_capabilities(result):
            if package_capability(current_package, capability) not in {"enabled", "assisted"}:
                return {"applied": False, "reason": "authorization_changed", "capability": capability, "result": dict(result)}
        reviewer_info = review.get("reviewer")
        if isinstance(reviewer_info, Mapping) and (
            reviewer_info.get("status") != "completed" or reviewer_info.get("timed_out")
        ):
            return {"applied": False, "reason": "reviewer_unavailable", "result": dict(result)}
        reviewer_result = reviewer_info.get("result") if isinstance(reviewer_info, Mapping) else None
        if not isinstance(reviewer_result, Mapping) or reviewer_result.get("status") != "rejected":
            return {"applied": False, "reason": "correction_requires_rejected_review", "result": dict(result)}
        reviewed_state_version = review.get("state_version")
        current_state_version = (result.get("state") or {}).get("version")
        if (
            reviewed_state_version is not None
            and current_state_version is not None
            and int(reviewed_state_version) != int(current_state_version)
        ):
            return {"applied": False, "reason": "state_changed_since_review", "result": dict(result)}
        if not isinstance(correction, Mapping) or not isinstance(correction.get("response"), str):
            return {"applied": False, "reason": "correction_requires_response", "result": dict(result)}
        original_action = result.get("action")
        corrected_action = correction.get("action", original_action)
        if corrected_action != original_action:
            return {"applied": False, "reason": "correction_cannot_change_action", "result": dict(result)}
        evidence = correction.get("evidence", result.get("evidence", []))
        if evidence != result.get("evidence", []):
            return {"applied": False, "reason": "evidence_changed", "result": dict(result)}
        if not self._evidence_current(str(event.get("business_id", "")), evidence):
            return {"applied": False, "reason": "evidence_changed", "result": dict(result)}
        reviewed_evidence_ids = review.get("evidence_ids")
        current_evidence_ids = [str(item.get("evidence_id")) for item in evidence if isinstance(item, Mapping)]
        if isinstance(reviewed_evidence_ids, list) and [str(item) for item in reviewed_evidence_ids] != current_evidence_ids:
            return {"applied": False, "reason": "evidence_association_changed", "result": dict(result)}
        if not self._covers_original_request(result, str(correction["response"])):
            return {"applied": False, "reason": "correction_drops_requested_topic", "result": dict(result)}
        unsupported_claims = self._unsupported_new_claims(
            str(result.get("response", "")), str(correction["response"]), evidence
        )
        revised_preview = dict(result)
        revised_preview["response"] = str(correction["response"])
        quality_failures = [
            name
            for name, value in self._quality_dimensions(revised_preview).items()
            if value is False
        ]
        unsupported_claims.extend(
            {"kind": "quality_dimension", "value": name}
            for name in quality_failures
            if not any(item.get("kind") == "quality_dimension" and item.get("value") == name for item in unsupported_claims)
        )
        if unsupported_claims:
            blocked_candidate = durable_key("candidate-correction-blocked", candidate, uuid.uuid4().hex)
            blocked_review = self.store.save_supervisor_review(
                {
                    "review_id": durable_key("supervisor-review-blocked", str(review.get("review_id", "")), uuid.uuid4().hex),
                    "candidate_id": blocked_candidate,
                    "original_candidate_id": candidate,
                    "parent_candidate_id": candidate,
                    "business_id": str(event.get("business_id", "")),
                    "conversation_id": str(event.get("conversation_id", "")),
                    "event_id": str(event.get("event_id", "")),
                    "package_version": package.get("package_version"),
                    "package_fingerprint": package_fingerprint(package),
                    "state_version": (result.get("state") or {}).get("version"),
                    "mode": self.mode,
                    "status": "correction_blocked",
                    "parent_review_id": review.get("review_id"),
                    "reason": "correction_fails_deterministic_revalidation"
                    if quality_failures and not any(item.get("kind") != "quality_dimension" for item in unsupported_claims)
                    else "correction_adds_unsupported_claim",
                    "claims": unsupported_claims,
                    "deterministic": self._deterministic_checks(result),
                }
            )
            return {
                "applied": False,
                "reason": "correction_fails_deterministic_revalidation"
                if quality_failures and not any(item.get("kind") != "quality_dimension" for item in unsupported_claims)
                else "correction_adds_unsupported_claim",
                "claims": unsupported_claims,
                "review": blocked_review,
                "result": dict(result),
            }
        self._corrections[candidate] = 1
        revised = dict(result)
        revised["response"] = str(correction["response"])
        revised["action"] = corrected_action
        revised["evidence"] = list(evidence) if isinstance(evidence, list) else list(result.get("evidence", []))
        revised["trace"] = list(result.get("trace", [])) + [{"type": "supervisor_correction", "candidate_id": candidate, "count": 1}]
        revised_candidate = durable_key("candidate-correction", candidate, "1")
        revised["candidate_id"] = revised_candidate
        audit = self.store.save_supervisor_review(
            {
                "review_id": durable_key("supervisor-review", revised_candidate),
                "candidate_id": revised_candidate,
                "original_candidate_id": candidate,
                "parent_candidate_id": candidate,
                "business_id": str(event.get("business_id", "")),
                "conversation_id": str(event.get("conversation_id", "")),
                "event_id": str(event.get("event_id", "")),
                "package_version": package.get("package_version"),
                "package_fingerprint": package_fingerprint(package),
                "state_version": (result.get("state") or {}).get("version"),
                "mode": self.mode,
                "status": "corrected",
                "correction_count": 1,
                "deterministic": self._deterministic_checks(revised),
                "quality_dimensions": self._quality_dimensions(revised),
                "evidence_ids": [str(item.get("evidence_id")) for item in revised["evidence"] if isinstance(item, Mapping)],
            }
        )
        return {"applied": True, "reason": "one_correction_revalidated", "result": revised, "review": audit}

    @staticmethod
    def _covers_original_request(result: Mapping[str, Any], response: str) -> bool:
        if not response.strip() and (result.get("action") is not None or result.get("response")):
            return False
        proposals = [
            item
            for item in result.get("trace", [])
            if isinstance(item, Mapping) and item.get("type") == "model_proposal"
        ]
        topics: list[str] = []
        for proposal in proposals:
            values = proposal.get("topics", [])
            if isinstance(values, list):
                topics.extend(str(value) for value in values)
        if not set(topics):
            return bool(response.strip()) or (result.get("action") is None and not result.get("response"))
        normalized = response.casefold()
        labels = {
            "guarantee": ("garantia",),
            "exchange": ("troca",),
            "return": ("devol", "reembolso"),
            "price": ("r$", "preço", "preco", "valor", "custa"),
            "access": ("acesso", "dura", "meses"),
            "delivery": ("entrega", "prazo", "envio"),
            "payment": ("pagamento", "pix", "cartão", "cartao"),
            "availability": ("estoque", "dispon", "tamanho"),
        }
        return all(any(term in normalized for term in labels.get(topic, (topic,))) for topic in set(topics))

    @staticmethod
    def _required_capabilities(result: Mapping[str, Any]) -> list[str]:
        required = []
        action = result.get("action") if isinstance(result.get("action"), Mapping) else {}
        action_capabilities = {
            "prepare_checkout": "checkout_prepare",
            "prepare_proposal": "quote",
            "human_transfer": "human_transfer",
        }
        capability = action_capabilities.get(str(action.get("type", "")))
        if capability:
            required.append(capability)
        for item in result.get("trace", []):
            if not isinstance(item, Mapping) or item.get("type") != "model_proposal":
                continue
            capability = {"price": "catalog_query", "knowledge": "knowledge_query"}.get(str(item.get("intent")))
            if capability and capability not in required:
                required.append(capability)
        return required

    @classmethod
    def _unsupported_new_claims(
        cls, original_response: str, corrected_response: str, evidence: Any
    ) -> list[Dict[str, str]]:
        original_claims = set(cls._commercial_claims(original_response))
        supported_claims = set()
        authorized_policy_claims = set(cls._policy_claims(original_response))
        if isinstance(evidence, list):
            for item in evidence:
                if isinstance(item, Mapping):
                    content = str(item.get("content", ""))
                    supported_claims.update(cls._commercial_claims(content))
                    authorized_policy_claims.update(cls._policy_claims(content))
        claims = [
            {"kind": kind, "value": value}
            for kind, value in cls._commercial_claims(corrected_response)
            if (kind, value) not in original_claims and (kind, value) not in supported_claims
        ]
        corrected_policy_claims = set(cls._policy_claims(corrected_response))
        for subject, polarity in corrected_policy_claims:
            opposite = "negative" if polarity == "positive" else "positive"
            if (subject, opposite) in authorized_policy_claims:
                claims.append({"kind": "contradictory_policy", "value": "%s:%s" % (subject, polarity)})
        return claims

    @staticmethod
    def _policy_claims(text: str) -> list[tuple[str, str]]:
        return policy_claims(text)

    @staticmethod
    def _commercial_claims(text: str) -> list[tuple[str, str]]:
        return commercial_claims(text)

    def _evidence_current(self, business_id: str, evidence: Any) -> bool:
        if not isinstance(evidence, list):
            return not evidence
        for item in evidence:
            if not isinstance(item, Mapping):
                return False
            row = next(
                (
                    found
                    for found in self.store.list_sources(business_id)
                    if str(found.get("evidence_id")) == str(item.get("evidence_id"))
                ),
                None,
            )
            if not row or row.get("status") != "approved" or row.get("review_status") != "approved" or not row.get("active"):
                return False
            for field in ("scope", "audience", "subject", "generation"):
                if field in item and str(row.get(field) or "") != str(item.get(field) or ""):
                    return False
            try:
                from datetime import datetime, timezone

                current = datetime.now(timezone.utc)
                valid_from = datetime.fromisoformat(str(row["valid_from"]).replace("Z", "+00:00")) if row.get("valid_from") else None
                valid_until = datetime.fromisoformat(str(row["valid_until"]).replace("Z", "+00:00")) if row.get("valid_until") else None
                if valid_from and valid_from.tzinfo is None:
                    valid_from = valid_from.replace(tzinfo=timezone.utc)
                if valid_until and valid_until.tzinfo is None:
                    valid_until = valid_until.replace(tzinfo=timezone.utc)
                if valid_from and valid_from.astimezone(timezone.utc) > current:
                    return False
                if valid_until and valid_until.astimezone(timezone.utc) <= current:
                    return False
            except (KeyError, TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _review_input(event: Mapping[str, Any], result: Mapping[str, Any], package: Mapping[str, Any]) -> Dict[str, Any]:
        state = result.get("state") if isinstance(result.get("state"), Mapping) else {}
        trace = result.get("trace", [])
        proposal = next(
            (item for item in reversed(trace) if isinstance(item, Mapping) and item.get("type") == "model_proposal"),
            {},
        )
        requested_offer_id = proposal.get("offer_id") or (state.get("facts") or {}).get("offer_id")
        offer_context = []
        for offer in package.get("offers", []):
            if not isinstance(offer, Mapping) or (requested_offer_id and str(offer.get("id")) != str(requested_offer_id)):
                continue
            offer_context.append(
                {
                    key: offer.get(key)
                    for key in ("id", "name", "kind", "mode", "price_type", "price", "currency", "description", "required_fields")
                    if key in offer
                }
            )
        allowed_fact_names = {
            "offer_id", "variant", "color", "quantity", "payment_method", "region", "scope", "site",
            "deadline_condition", "confirmation",
        }
        facts = state.get("facts") if isinstance(state.get("facts"), Mapping) else {}
        safe_facts = {key: facts[key] for key in allowed_fact_names if key in facts}
        evidence = []
        for item in result.get("evidence", []):
            if not isinstance(item, Mapping):
                continue
            evidence.append(
                {
                    key: item.get(key)
                    for key in ("evidence_id", "source_id", "source_version", "scope", "audience", "subject", "generation", "valid_from", "valid_until", "content")
                    if key in item
                }
            )
            evidence[-1]["content"] = str(evidence[-1].get("content", ""))[:2_000]
        return {
            "event_id": event.get("event_id"),
            "request": str(event.get("text", ""))[:4_000],
            "request_truncated": len(str(event.get("text", ""))) > 4_000,
            "response": result.get("response", ""),
            "action_type": (result.get("action") or {}).get("type"),
            "action": {
                key: (result.get("action") or {}).get(key)
                for key in ("type", "status", "effect_key", "quote_id", "proposal_id", "checkout_id", "charged")
                if key in (result.get("action") or {})
            },
            "topics": list(proposal.get("topics", [])) if isinstance(proposal.get("topics"), list) else [],
            "state": {
                "version": state.get("version"),
                "profile": state.get("profile"),
                "phase": state.get("phase"),
                "intent": state.get("intent"),
                "pending": state.get("pending"),
                "operation": {
                    key: (state.get("operation") or {}).get(key)
                    for key in ("type", "status", "effect_key", "payment_status")
                    if key in (state.get("operation") or {})
                },
                "facts": safe_facts,
            },
            "package": {
                "version": package.get("package_version"),
                "fingerprint": package_fingerprint(package),
                "offers": offer_context,
                "policies": {
                    key: package.get("policies", {}).get(key)
                    for key in ("conversation", "quote", "follow_up")
                    if isinstance(package.get("policies", {}).get(key), Mapping)
                },
                "capabilities": {
                    str(key): value.get("state")
                    for key, value in package.get("capabilities", {}).items()
                    if isinstance(value, Mapping)
                },
            },
            "evidence": evidence,
        }

    @staticmethod
    def _state_control_snapshot(state: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            key: state.get(key)
            for key in ("responsible", "status", "phase", "pending", "operation", "quote", "follow_up_allowed", "facts")
        }

    @staticmethod
    def _deterministic_checks(result: Mapping[str, Any]) -> Dict[str, Any]:
        response = str(result.get("response", ""))
        evidence = result.get("evidence") or []
        return {
            "response_present_or_silent": bool(response) or result.get("action") is None,
            "evidence_referenced": bool(evidence) or not any(item.get("type") == "evidence_used" for item in result.get("trace", []) if isinstance(item, Mapping)),
            "action_type": (result.get("action") or {}).get("type"),
        }

    @staticmethod
    def _quality_dimensions(result: Mapping[str, Any]) -> Dict[str, bool]:
        response = str(result.get("response", ""))
        state = result.get("state") if isinstance(result.get("state"), Mapping) else {}
        history = state.get("history", []) if isinstance(state, Mapping) else []
        previous_responses = {
            str(item.get("response"))
            for item in history[:-1]
            if isinstance(item, Mapping) and item.get("response")
        }
        trace = result.get("trace", [])
        evidence_used = any(item.get("type") == "evidence_used" for item in trace if isinstance(item, Mapping))
        tone_is_safe = not bool(re.search(r"última chance|ultima chance|compre agora ou perca|garantido", response.casefold()))
        requested_topics = []
        for item in trace:
            if isinstance(item, Mapping) and item.get("type") == "model_proposal" and isinstance(item.get("topics"), list):
                requested_topics.extend(str(topic) for topic in item["topics"])
        labels = {
            "guarantee": ("garantia",),
            "exchange": ("troca",),
            "return": ("devol", "reembolso"),
            "price": ("r$", "preço", "preco", "valor", "custa"),
            "access": ("acesso", "dura", "meses"),
            "delivery": ("entrega", "prazo", "envio"),
            "payment": ("pagamento", "pix", "cartao", "cartão"),
            "availability": ("estoque", "dispon", "tamanho"),
        }
        # A pending state proves that the motor stopped safely; it does not
        # prove that the buyer's requested topic was answered.  The response
        # (or a concrete action when there is no textual topic) must still
        # cover every requested topic.
        request_covered = bool(response or result.get("action")) and all(
            any(term in response.casefold() for term in labels.get(topic, (topic,)))
            for topic in set(requested_topics)
        )
        return {
            "request_coverage": request_covered,
            "repetition": not response or response not in previous_responses,
            "evidence_support": not evidence_used or bool(result.get("evidence")),
            "tone": tone_is_safe,
        }

    @staticmethod
    def _comparison(
        reviews: list[Mapping[str, Any]], *, cost: float, latency_ms: float, deterministic_failures: int
    ) -> Dict[str, Any]:
        primary_reviews = QualitySupervisor._primary_reviews(reviews)
        by_candidate = {QualitySupervisor._candidate_root(item): item for item in primary_reviews}
        final_reviews = dict(by_candidate)
        for item in reviews:
            if str(item.get("status", "")) != "corrected":
                continue
            root = QualitySupervisor._candidate_root(item)
            if root in by_candidate:
                # A correction is an outcome for the original candidate, not
                # an additional supervised case.  Keep the original id as the
                # key so both sides of the comparison share one denominator.
                final_reviews[root] = item
        baseline_failures = sum(
            1 for item in primary_reviews if QualitySupervisor._has_deterministic_failure(item)
        )
        supervised_failures = sum(
            1 for item in final_reviews.values() if QualitySupervisor._has_deterministic_failure(item)
        )
        # Older persisted reports may contain no primary row.  Preserve the
        # caller's aggregate in that migration-only case without allowing
        # correction audit rows to inflate the denominator.
        if not primary_reviews:
            supervised_failures = int(deterministic_failures)
        return {
            "comparable": True,
            "baseline": {
                "cases": len(primary_reviews),
                "deterministic_failures": baseline_failures,
                "cost": 0,
                "latency_ms": 0,
            },
            "supervised": {
                # Both denominators describe the same original candidate
                # cohort; correction audit rows are outcomes, not new cases.
                "cases": len(primary_reviews),
                "deterministic_failures": supervised_failures,
                "cost": int(cost) if cost.is_integer() else round(cost, 6),
                "latency_ms": round(latency_ms, 3),
            },
            "candidate_ids": sorted(by_candidate),
            "disable_without_migration": True,
        }

    @staticmethod
    def _public_review(review: Mapping[str, Any]) -> Dict[str, Any]:
        value = {
            "status": str(review.get("status", "unknown")),
            "issues": list(review.get("issues", []))[:20] if isinstance(review.get("issues", []), list) else [],
            "false_positive": bool(review.get("false_positive", False)),
            "correction": review.get("correction") if isinstance(review.get("correction"), Mapping) else None,
        }
        if isinstance(review.get("cost"), (int, float)) and not isinstance(review.get("cost"), bool):
            value["cost"] = review["cost"]
        return value
