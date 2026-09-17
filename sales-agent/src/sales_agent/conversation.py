"""The policy-controlled conversation engine.

The engine accepts one channel event and returns a durable result. Model output
is a proposal only; every question, transition and external effect is checked
here against the active package and the connector contracts.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .commerce import CommerceError, SimulatedCommerce
from .knowledge import KnowledgeBackend, PersistentFarolKnowledge
from .model import ModelAdapter, RuleBasedModel
from .storage import StateStore
from .types import EngineResult, Proposal
from .validation import package_capability


class ConversationError(ValueError):
    pass


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
    ):
        self.store = store
        self.model = model or RuleBasedModel()
        self.knowledge = knowledge or PersistentFarolKnowledge(store)
        self.commerce = commerce or SimulatedCommerce(store)
        self.before_send = before_send
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
            state = result.state
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
            latest = self.store.load_conversation(business_id, conversation_id, str(event["contact_id"]))
            if int(latest.get("version", 0)) != starting_version:
                # A correction or human takeover won while this response was
                # being prepared. Persist the event for audit, but do not put
                # the stale response or effect in the outbox.
                stale_action = result.action
                result.state = latest
                result.response = ""
                result.action = None
                if stale_action is not None:
                    latest["pending"] = {
                        "type": "post_effect_correction",
                        "reason": "correction arrived after external effect",
                        "effect": stale_action,
                    }
                    latest["operation"] = {"type": stale_action.get("type"), "status": "unknown", "effect": stale_action}
                    latest["phase"] = "action_in_progress"
                    latest["version"] = int(latest.get("version", 0)) + 1
                    result.state = latest
                    result.response = "A condição mudou enquanto eu processava. A operação foi registrada para conciliação antes de qualquer novo passo."
                    self.store.save_conversation(latest)
                result.trace = result.trace + [
                    {
                        "type": "stale_response_suppressed",
                        "starting_version": starting_version,
                        "current_version": latest.get("version"),
                    }
                ]
                payload = result.as_dict()
                self.store.save_event(business_id, conversation_id, event_id, dict(event), payload)
                return result
            payload = result.as_dict()
            self.store.save_conversation(state)
            self.store.enqueue_message(
                "%s:%s" % (business_id, event_id),
                business_id,
                conversation_id,
                {"event_id": event_id, "response": result.response, "action": result.action},
            )
            inserted = self.store.save_event(business_id, conversation_id, event_id, dict(event), payload)
            if not inserted:
                replay = self.store.get_event(business_id, conversation_id, event_id) or payload
                replay["duplicate"] = True
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
            return result

    def schedule_follow_up(self, business_id: str, conversation_id: str, task_id: str, message: str) -> Dict[str, Any]:
        """Queue a follow-up intent; sending is revalidated at the call site."""
        state = self.store.load_conversation(business_id, conversation_id, "unknown")
        scheduled = self.store.enqueue_message(
            "followup:%s" % task_id,
            business_id,
            conversation_id,
            {"task_id": task_id, "message": message, "status": "scheduled"},
        ) if self._follow_up_eligible(state) else False
        return {"scheduled": scheduled, "task_id": task_id, "eligible_now": self._follow_up_eligible(state)}

    def revalidate_follow_up(self, business_id: str, conversation_id: str, task_id: str) -> Dict[str, Any]:
        """Recheck the persisted conversation immediately before delivery."""
        state = self.store.load_conversation(business_id, conversation_id, "unknown")
        eligible = self._follow_up_eligible(state)
        reason = "eligible" if eligible else "conversation no longer eligible"
        if not eligible:
            self.store.cancel_followup(task_id)
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
            if not str(event.get(field, "")).strip():
                raise ConversationError("evento sem campo obrigatório: %s" % field)

    def _decide(self, package: Mapping[str, Any], state: Dict[str, Any], event: Mapping[str, Any]) -> EngineResult:
        text = str(event["text"])
        trace: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []
        action: Optional[Dict[str, Any]] = None

        # A human owner has precedence over every model proposal.
        if state.get("responsible") == "human" or state.get("status") == "human_paused":
            return EngineResult(
                event_id=str(event["event_id"]),
                conversation_id=str(event["conversation_id"]),
                response="A conversa está aguardando atendimento humano. Não vou enviar novas mensagens automáticas.",
                state=state,
                trace=[{"type": "human_pause_respected"}],
            )

        proposal = self.model.propose(text, package, state)
        trace.append(
            {
                "type": "model_proposal",
                "model": proposal.model_name,
                "intent": proposal.intent,
                "offer_id": proposal.offer_id,
                "requested_action": proposal.requested_action,
            }
        )
        offer = self._offer(package, proposal.offer_id)
        if proposal.offer_id and not offer:
            trace.append({"type": "proposal_rejected", "reason": "offer_not_in_package"})
            proposal.offer_id = None
        self._merge_safe_facts(state, proposal, offer, trace)

        if proposal.intent == "stop":
            self.store.cancel_followups(str(package["business"]["id"]), str(state["conversation_id"]))
            state["follow_up_allowed"] = False
            state["responsible"] = "ai"
            state["status"] = "closed_without_sale"
            state["phase"] = "encerrado_sem_venda"
            state["pending"] = None
            return self._result(event, state, "Entendido. Não vou enviar novas mensagens comerciais.", trace=trace)

        if proposal.intent == "human":
            self.store.cancel_followups(str(package["business"]["id"]), str(state["conversation_id"]))
            pending_context = state.get("pending")
            state["responsible"] = "human"
            state["status"] = "human_paused"
            state["phase"] = "transferido"
            state["pending"] = None
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
            return self._result(event, state, "Vou encaminhar você para uma pessoa, sem pedir outra qualificação.", action, trace)

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
            if not offer:
                offer = self._offer(package, state.get("facts", {}).get("offer_id"))
            query = text
            hits = self.knowledge.search(str(package["business"]["id"]), query, 5)
            evidence = [dict(hit) for hit in hits]
            if not hits:
                state["pending"] = {"type": "evidence", "reason": "no_authorized_source"}
                return self._result(
                    event,
                    state,
                    "Não encontrei uma fonte aprovada para confirmar isso agora. Vou encaminhar a dúvida sem inventar uma resposta.",
                    trace=trace + [{"type": "evidence_missing"}],
                    evidence=evidence,
                )
            if self._material_conflict(hits):
                state["pending"] = {"type": "evidence", "reason": "material_conflict"}
                return self._result(
                    event,
                    state,
                    "Encontrei condições conflitantes e não vou escolher uma arbitrariamente. Preciso confirmar qual política está vigente.",
                    trace=trace + [{"type": "evidence_conflict", "hits": len(hits)}],
                    evidence=evidence,
                )
            content = hits[0]["content"]
            response = self._evidence_answer(text, content)
            return self._result(event, state, response, trace=trace + [{"type": "evidence_used", "evidence_id": hits[0]["evidence_id"]}], evidence=evidence)

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

        missing = self._missing_for_offer(offer, state["facts"], str(event["contact_id"]))
        if missing:
            reason = self._reason_for_field(missing, offer)
            return self._ask(event, state, offer, missing, reason, trace)

        if offer.get("mode") in {"consultative", "proposal", "appointment"} or offer.get("price_type") == "on_request":
            if (state.get("pending") or {}).get("type") == "quote_confirmation" and not state["facts"].get("confirmation"):
                return self._result(event, state, "O escopo está pronto. Confirma que posso preparar a proposta?", trace=trace)
            result = self.commerce.prepare_proposal(
                package,
                offer["id"],
                state["facts"],
                business_id=package["business"]["id"],
                conversation_id=state["conversation_id"],
            )
            state["operation"] = {"type": "proposal", "status": "confirmed", **result}
            state["phase"] = "action_in_progress"
            state["pending"] = None
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
            )
        except CommerceError as exc:
            trace.append({"type": "checkout_result", "status": exc.status, "code": exc.code})
            if exc.status == "pending" and exc.code == "identity_not_verified":
                state["pending"] = {"type": "identity", "reason": "checkout requires verified contact"}
                return self._result(event, state, "Para preparar o checkout, preciso confirmar a identificação do comprador. Qual e-mail devo usar?", trace=trace)
            if exc.status == "unknown":
                state["operation"] = {"type": "checkout", "status": "unknown", "quote_id": new_quote["id"]}
                state["pending"] = {"type": "reconcile_checkout"}
                return self._result(event, state, "O provedor não confirmou o resultado do checkout. Não vou repetir a operação; preciso conciliá-la antes de informar um link.", trace=trace)
            return self._result(event, state, "Não consegui preparar o checkout: %s" % str(exc), trace=trace)

        state["operation"] = {"type": "checkout", "status": "confirmed", **checkout}
        state["phase"] = "action_in_progress"
        state["pending"] = None
        state["facts"].pop("confirmation", None)
        action = {"type": "prepare_checkout", **checkout}
        response = "O %s custa R$ %.2f. Você pode concluir aqui: %s" % (offer["name"], new_quote["amount"], checkout["url"])
        trace.append({"type": "checkout_prepared", "charged": checkout.get("charged", False)})
        return self._result(event, state, response, action, trace)

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
        state: Dict[str, Any], proposal: Proposal, offer: Optional[Mapping[str, Any]], trace: List[Dict[str, Any]]
    ) -> None:
        allowed = {"offer_id", "variant", "color", "quantity", "payment_method", "email", "region", "company_name", "scope", "site", "deadline_condition", "delivery", "confirmation"}
        changed = {}
        for key, value in proposal.facts.items():
            if key not in allowed or value in (None, ""):
                continue
            if state["facts"].get(key) != value:
                changed[key] = {"old": state["facts"].get(key), "new": value}
                state["facts"][key] = value
        if proposal.offer_id and offer:
            if state["facts"].get("offer_id") != offer["id"]:
                changed["offer_id"] = {"old": state["facts"].get("offer_id"), "new": offer["id"]}
            state["facts"]["offer_id"] = offer["id"]
        if changed:
            trace.append({"type": "facts_updated", "changed": changed})

    @staticmethod
    def _quote_changed(old: Optional[Mapping[str, Any]], new: Mapping[str, Any]) -> bool:
        if not old:
            return False
        fields = ("offer_id", "quantity", "variant", "payment_method", "region", "amount")
        return any(old.get(field) != new.get(field) for field in fields)

    @staticmethod
    def _missing_for_offer(offer: Mapping[str, Any], facts: Mapping[str, Any], contact_id: str) -> Optional[str]:
        for field in offer.get("required_fields", []):
            if not facts.get(field):
                return str(field)
        if offer.get("mode") == "direct" and not contact_id.startswith("verified:") and not facts.get("email"):
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
    def _material_conflict(hits: List[Mapping[str, Any]]) -> bool:
        if len(hits) < 2:
            return False
        sources = {str(hit.get("source_id")) for hit in hits}
        combined = " ".join(str(hit.get("content", "")) for hit in hits)
        prices = set(re.findall(r"r\$\s*([\d.,]+)", combined, re.I))
        durations = set(re.findall(r"\b(\d+)\s*(?:dias?|meses?|semanas?)\b", combined, re.I))
        return len(sources) > 1 and (len(prices) > 1 or len(durations) > 1)

    @staticmethod
    def _evidence_answer(question: str, content: str) -> str:
        if "acesso" in question.casefold() or "acesso" in content.casefold():
            return content
        return content

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
