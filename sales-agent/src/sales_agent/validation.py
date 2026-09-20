"""Validation for business packages and persisted configuration."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from numbers import Real
from typing import Any, Dict, Mapping


class PackageError(ValueError):
    """A business package cannot be activated safely."""


def package_fingerprint(package: Mapping[str, Any]) -> str:
    """Return a stable digest for the complete persisted package.

    ``package_version`` is an owner-facing label and is not required to be
    unique.  Pilot admission therefore also records this content digest so a
    material edit with a reused label cannot inherit an older evaluation.
    """

    canonical = json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:%s" % hashlib.sha256(canonical).hexdigest()


CAPABILITY_STATES = {"enabled", "assisted", "disabled", "pending"}
OFFER_KINDS = {"physical", "digital", "service"}
MODES = {"direct", "consultative", "proposal", "appointment"}


def _require(value: Any, path: str) -> None:
    if value is None or value == "":
        raise PackageError("campo obrigatório ausente: %s" % path)


def _non_negative_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PackageError("%s deve ser um número" % path)
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise PackageError("%s deve ser finito e não negativo" % path)
    return numeric


def validate_package(package: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy after checking safety-critical package invariants."""

    if not isinstance(package, Mapping):
        raise PackageError("pacote deve ser um objeto JSON")
    for field in ("schema_version", "package_version", "business", "offers", "policies", "capabilities", "sources", "skills"):
        _require(package.get(field), field)
    if package.get("schema_version") != 1:
        raise PackageError("schema_version não suportado")
    business = package["business"]
    if not isinstance(business, Mapping):
        raise PackageError("business deve ser um objeto")
    for field in ("id", "name", "buyer_types"):
        _require(business.get(field), "business.%s" % field)
    if not isinstance(business["id"], str) or not isinstance(business["name"], str):
        raise PackageError("business.id e business.name devem ser texto")
    if (
        not isinstance(business["buyer_types"], list)
        or not business["buyer_types"]
        or not all(isinstance(item, str) and item for item in business["buyer_types"])
    ):
        raise PackageError("business.buyer_types deve ser uma lista não vazia")
    if len(set(business["buyer_types"])) != len(business["buyer_types"]):
        raise PackageError("business.buyer_types contém valores duplicados")
    if not isinstance(package["policies"], Mapping):
        raise PackageError("policies deve ser um objeto")
    conversation_policy = package["policies"].get("conversation", {})
    if conversation_policy and not isinstance(conversation_policy, Mapping):
        raise PackageError("policies.conversation deve ser um objeto")
    if isinstance(conversation_policy, Mapping):
        preference_transitions = conversation_policy.get("preference_transitions", [])
        if not isinstance(preference_transitions, list):
            raise PackageError("policies.conversation.preference_transitions deve ser uma lista")
        preference_ids = set()
        for index, transition in enumerate(preference_transitions):
            path = "policies.conversation.preference_transitions[%d]" % index
            if not isinstance(transition, Mapping):
                raise PackageError("%s deve ser um objeto" % path)
            for field in ("id", "profile", "objective", "source"):
                if not isinstance(transition.get(field), str) or not transition[field].strip():
                    raise PackageError("%s.%s deve ser texto não vazio" % (path, field))
            terms = transition.get("terms", [])
            if not isinstance(terms, list) or not terms or not all(isinstance(term, str) and term.strip() for term in terms):
                raise PackageError("%s.terms deve ser uma lista de textos" % path)
            if transition["id"] in preference_ids:
                raise PackageError("preferência duplicada: %s" % transition["id"])
            preference_ids.add(transition["id"])
    offers = package["offers"]
    if not isinstance(offers, list) or not offers:
        raise PackageError("offers deve ser uma lista não vazia")
    offer_ids = set()
    for index, offer in enumerate(offers):
        path = "offers[%d]" % index
        if not isinstance(offer, Mapping):
            raise PackageError("%s deve ser um objeto" % path)
        for field in ("id", "name", "kind", "mode", "currency"):
            _require(offer.get(field), "%s.%s" % (path, field))
            if not isinstance(offer.get(field), str):
                raise PackageError("%s.%s deve ser texto" % (path, field))
        if offer["id"] in offer_ids:
            raise PackageError("oferta duplicada: %s" % offer["id"])
        offer_ids.add(offer["id"])
        if offer["kind"] not in OFFER_KINDS:
            raise PackageError("%s.kind inválido" % path)
        if offer["mode"] not in MODES:
            raise PackageError("%s.mode inválido" % path)
        if offer.get("price_type", "fixed") not in {"fixed", "variable", "on_request"}:
            raise PackageError("%s.price_type inválido" % path)
        if offer.get("price_type", "fixed") == "fixed":
            if "price" not in offer:
                raise PackageError("campo obrigatório ausente: %s.price" % path)
            _non_negative_number(offer["price"], "%s.price" % path)
        required_fields = offer.get("required_fields", [])
        if not isinstance(required_fields, list) or not all(isinstance(item, str) and item for item in required_fields):
            raise PackageError("%s.required_fields deve ser uma lista" % path)
        if len(set(required_fields)) != len(required_fields):
            raise PackageError("%s.required_fields contém valores duplicados" % path)
        aliases = offer.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
            raise PackageError("%s.aliases deve ser uma lista de textos" % path)
        if "quote_validity_minutes" in offer and (
            isinstance(offer["quote_validity_minutes"], bool)
            or not isinstance(offer["quote_validity_minutes"], int)
            or offer["quote_validity_minutes"] <= 0
        ):
            raise PackageError("%s.quote_validity_minutes deve ser inteiro positivo" % path)
        if "delivery_days" in offer and (
            isinstance(offer["delivery_days"], bool)
            or not isinstance(offer["delivery_days"], int)
            or offer["delivery_days"] < 0
        ):
            raise PackageError("%s.delivery_days deve ser inteiro não negativo" % path)
        if offer["kind"] == "physical":
            stock = offer.get("stock", {})
            if not isinstance(stock, Mapping):
                raise PackageError("%s.stock deve ser um objeto" % path)
            for variant, amount in stock.items():
                if not isinstance(variant, str) or not variant:
                    raise PackageError("%s.stock contém variante inválida" % path)
                if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                    raise PackageError("%s.stock.%s deve ser inteiro não negativo" % (path, variant))
    capabilities = package["capabilities"]
    if not isinstance(capabilities, Mapping):
        raise PackageError("capabilities deve ser um objeto")
    for name, entry in capabilities.items():
        if not isinstance(entry, Mapping) or entry.get("state") not in CAPABILITY_STATES:
            raise PackageError("capability %s precisa de state válido" % name)
        if entry["state"] in {"disabled", "pending"} and not entry.get("reason"):
            raise PackageError("capability %s precisa explicar sua lacuna" % name)
        if "reason" in entry and not isinstance(entry["reason"], str):
            raise PackageError("capability %s precisa de reason textual" % name)
    settings = package.get("settings", {})
    if not isinstance(settings, Mapping):
        raise PackageError("settings deve ser um objeto")
    skill_context_budget = settings.get("skill_context_budget", 8_000)
    if (
        isinstance(skill_context_budget, bool)
        or not isinstance(skill_context_budget, int)
        or skill_context_budget <= 0
        or skill_context_budget > 64_000
    ):
        raise PackageError("settings.skill_context_budget deve ser inteiro entre 1 e 64000")
    lifecycle = package.get("lifecycle", "active")
    if lifecycle not in {"draft", "active"}:
        raise PackageError("lifecycle deve ser draft ou active")
    if lifecycle == "draft":
        for name in (
            "catalog_query",
            "quote",
            "checkout_prepare",
            "payment_charge",
            "human_transfer",
            "knowledge_query",
            "follow_up",
        ):
            if package.get("capabilities", {}).get(name, {}).get("state") in {"enabled", "assisted"}:
                raise PackageError("rascunho não pode habilitar capability %s" % name)
    sources = package["sources"]
    if not isinstance(sources, list):
        raise PackageError("sources deve ser uma lista")
    source_keys = set()
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise PackageError("sources[%d] deve ser um objeto" % index)
        for field in ("id", "version", "status", "content"):
            _require(source.get(field), "sources[%d].%s" % (index, field))
            if not isinstance(source.get(field), str):
                raise PackageError("sources[%d].%s deve ser texto" % (index, field))
        if len(source["content"].encode("utf-8")) > 5_000_000:
            raise PackageError("conteúdo da fonte excede 5 MB")
        source_key = (source["id"], source["version"])
        if source_key in source_keys:
            raise PackageError("fonte duplicada: %s@%s" % source_key)
        source_keys.add(source_key)
        if source["status"] not in {"approved", "revoked", "pending"}:
            raise PackageError("status de fonte inválido")
        if source["status"] == "approved" and not source.get("origin"):
            raise PackageError("fonte aprovada precisa de origin")
        if "origin" in source and not isinstance(source["origin"], str):
            raise PackageError("origin da fonte deve ser texto")
        for field in ("locator", "scope", "audience", "subject", "generation"):
            if field in source and source[field] is not None and not isinstance(source[field], str):
                raise PackageError("sources[%d].%s deve ser texto" % (index, field))
        parsed_validity = {}
        for field in ("valid_from", "valid_until"):
            if field in source and source[field] is not None:
                if not isinstance(source[field], str):
                    raise PackageError("sources[%d].%s deve ser texto ISO" % (index, field))
                try:
                    parsed = datetime.fromisoformat(source[field].replace("Z", "+00:00"))
                except ValueError as exc:
                    raise PackageError("sources[%d].%s não é data ISO" % (index, field)) from exc
                parsed_validity[field] = parsed
        if parsed_validity.get("valid_from") and parsed_validity.get("valid_until"):
            start = parsed_validity["valid_from"]
            end = parsed_validity["valid_until"]
            if (start.tzinfo is None and end.tzinfo is not None) or (start.tzinfo is not None and end.tzinfo is None):
                raise PackageError("sources[%d].valid_from e valid_until precisam usar o mesmo tipo de fuso" % index)
            if start >= end:
                raise PackageError("sources[%d].vigência tem intervalo inválido" % index)
        if "active" in source and not isinstance(source["active"], bool):
            raise PackageError("sources[%d].active deve ser booleano" % index)
    skills = package["skills"]
    if not isinstance(skills, list) or not all(isinstance(item, Mapping) for item in skills):
        raise PackageError("skills deve ser uma lista de objetos")
    # A declared skill is metadata, not a permission, but an unknown or
    # unavailable reference must never be reported as loaded.  Import lazily
    # to keep the validation module independent from the catalog at import
    # time.
    from .skills import SkillCatalog

    catalog = {item["id"]: item for item in SkillCatalog().list_skills()}
    seen_skill_ids = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill.get("id"), str) or not skill["id"].strip():
            raise PackageError("skills[%d].id deve ser texto não vazio" % index)
        skill_id = str(skill["id"])
        record = catalog.get(skill_id)
        if record is None:
            raise PackageError("skill desconhecida: %s" % skill_id)
        if record.get("audience") != "buyer-attention":
            raise PackageError("skill %s não é compatível com atendimento comprador: %s" % (skill_id, record.get("audience")))
        if not record.get("available"):
            raise PackageError("skill indisponível: %s" % skill_id)
        for field in ("version", "when"):
            if field in skill and (not isinstance(skill[field], str) or not skill[field].strip()):
                raise PackageError("skills[%d].%s deve ser texto não vazio" % (index, field))
        if "version" in skill and str(skill["version"]) != str(record["version"]):
            raise PackageError("versão incompatível da skill: %s" % skill_id)
        if "context_chars" in skill and (
            isinstance(skill["context_chars"], bool)
            or not isinstance(skill["context_chars"], int)
            or skill["context_chars"] <= 0
            or skill["context_chars"] > skill_context_budget
        ):
            raise PackageError("skills[%d].context_chars excede o orçamento" % index)
        if skill_id in seen_skill_ids:
            raise PackageError("skill duplicada: %s" % skill_id)
        seen_skill_ids.add(skill_id)
    copied = {key: value for key, value in package.items()}
    return copied


def package_capability(package: Mapping[str, Any], name: str) -> str:
    entry = package.get("capabilities", {}).get(name, {})
    state = str(entry.get("state", "disabled"))
    if package.get("lifecycle", "active") == "draft" and state in {"enabled", "assisted"}:
        return "pending"
    return state
