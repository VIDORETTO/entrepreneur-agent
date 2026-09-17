"""Contracts and simulators for catalog, quote, checkout and proposal effects."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional

from .storage import StateStore


class CommerceError(RuntimeError):
    def __init__(self, code: str, message: str, status: str = "failed"):
        self.code = code
        self.status = status
        super().__init__(message)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


class SimulatedCommerce:
    """Persistent simulator with the same guard rails expected of a real adapter."""

    name = "simulated-commerce-v1"

    def __init__(self, store: StateStore):
        self.store = store
        self.behavior: Dict[str, Any] = {}

    def set_behavior(self, name: str, value: Any) -> None:
        self.behavior[name] = value

    def offer(self, package: Mapping[str, Any], offer_id: str) -> Optional[Dict[str, Any]]:
        for offer in package.get("offers", []):
            if offer.get("id") == offer_id:
                return dict(offer)
        return None

    def quote(
        self,
        package: Mapping[str, Any],
        offer_id: str,
        facts: Mapping[str, Any],
        *,
        conversation_id: str,
    ) -> Dict[str, Any]:
        offer = self.offer(package, offer_id)
        if not offer:
            raise CommerceError("offer_not_found", "oferta não encontrada")
        quantity = int(facts.get("quantity", 1))
        if quantity <= 0:
            raise CommerceError("invalid_quantity", "quantidade inválida")
        if offer.get("price_type", "fixed") != "fixed":
            raise CommerceError("quote_required", "esta oferta depende de avaliação", "pending")
        amount = round(float(offer["price"]) * quantity, 2)
        if offer.get("payment_adjustments", {}).get(facts.get("payment_method")):
            amount = round(amount * float(offer["payment_adjustments"][facts["payment_method"]]), 2)
        quote_payload = {
            "offer_id": offer_id,
            "quantity": quantity,
            "variant": facts.get("variant"),
            "payment_method": facts.get("payment_method", "pix"),
            "region": facts.get("region"),
            "amount": amount,
            "currency": offer.get("currency", "BRL"),
        }
        quote_id = "q_%s" % _hash({"conversation": conversation_id, **quote_payload})
        validity = int(offer.get("quote_validity_minutes", 30))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=validity)
        return {
            "id": quote_id,
            **quote_payload,
            "valid_until_minutes": validity,
            "expires_at": expires_at.isoformat(timespec="seconds"),
            "source": "simulated-catalog",
            "status": "valid",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def check_delivery(self, package: Mapping[str, Any], offer_id: str, facts: Mapping[str, Any]) -> Dict[str, Any]:
        offer = self.offer(package, offer_id)
        if not offer:
            raise CommerceError("offer_not_found", "oferta não encontrada")
        forced = self.behavior.get("delivery")
        if forced is not None:
            return dict(forced)
        if facts.get("deadline_condition") and not offer.get("delivery_guaranteed_by"):
            return {"status": "pending", "reason": "deadline requires an operational confirmation"}
        days = int(offer.get("delivery_days", 5))
        return {"status": "confirmed", "business_days": days, "region": facts.get("region")}

    def prepare_checkout(
        self,
        package: Mapping[str, Any],
        offer_id: str,
        facts: Mapping[str, Any],
        quote: Mapping[str, Any],
        *,
        business_id: str,
        conversation_id: str,
        contact_id: str,
    ) -> Dict[str, Any]:
        if not quote or quote.get("status") != "valid":
            raise CommerceError("quote_required", "cotação válida é obrigatória")
        expires_at = quote.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                    raise CommerceError("quote_expired", "a cotação expirou; preciso recalcular")
            except ValueError:
                raise CommerceError("quote_invalid", "validade da cotação não pôde ser verificada")
        if not facts.get("quantity"):
            raise CommerceError("quantity_required", "quantidade é obrigatória")
        if not contact_id.startswith("verified:"):
            raise CommerceError("identity_not_verified", "identificação do comprador ainda não foi verificada", "pending")
        effect_key = "checkout:%s:%s:%s" % (business_id, conversation_id, quote["id"])
        created, existing = self.store.reserve_effect(
            effect_key,
            "checkout",
            {"business_id": business_id, "conversation_id": conversation_id, "quote_id": quote["id"]},
        )
        if not created:
            if existing.get("status") in {"unknown", "reserved"}:
                if existing.get("status") == "reserved":
                    self.store.update_effect(effect_key, "unknown", {**existing, "reason": "interrupted before confirmation"})
                raise CommerceError("effect_unknown", "checkout anterior tem resultado desconhecido", "unknown")
            return existing
        offer = self.offer(package, offer_id) or {}
        if offer.get("kind") == "physical":
            variant = str(facts.get("variant", "default"))
            if not self.store.reserve_inventory(business_id, offer_id, variant, int(facts.get("quantity", 1))):
                self.store.update_effect(effect_key, "failed", {"reason": "out_of_stock", "quote_id": quote["id"]})
                raise CommerceError("out_of_stock", "essa combinação não está disponível")
        if self.behavior.get("checkout_timeout"):
            self.store.update_effect(effect_key, "unknown", {"quote_id": quote["id"], "effect_key": effect_key})
            raise CommerceError("effect_unknown", "o provedor não confirmou o resultado do checkout", "unknown")
        checkout_id = "co_%s" % _hash({"effect_key": effect_key})
        result = {
            "status": "prepared",
            "checkout_id": checkout_id,
            "url": "https://checkout.invalid/%s" % checkout_id,
            "quote_id": quote["id"],
            "charged": False,
            "effect_key": effect_key,
        }
        self.store.update_effect(effect_key, "confirmed", result)
        return result

    def query_effect(self, effect_key: str) -> Optional[Dict[str, Any]]:
        return self.store.get_effect(effect_key)

    def prepare_proposal(
        self,
        package: Mapping[str, Any],
        offer_id: str,
        facts: Mapping[str, Any],
        *,
        business_id: str,
        conversation_id: str,
    ) -> Dict[str, Any]:
        key = "proposal:%s:%s" % (business_id, conversation_id)
        created, existing = self.store.reserve_effect(key, "proposal", {"offer_id": offer_id})
        if not created:
            return existing
        proposal_id = "pr_%s" % _hash({"key": key, "facts": dict(facts)})
        result = {"status": "prepared", "proposal_id": proposal_id, "sent": False, "effect_key": key}
        self.store.update_effect(key, "confirmed", result)
        return result

    def lookup_payment(self, effect_key: str) -> Dict[str, Any]:
        effect = self.store.get_effect(effect_key)
        if effect and effect.get("payment_status"):
            return effect
        return {"status": "pending", "payment_confirmed": False, "effect_key": effect_key}
