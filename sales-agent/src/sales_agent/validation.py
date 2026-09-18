"""Validation for business packages and persisted configuration."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Dict, Mapping


class PackageError(ValueError):
    """A business package cannot be activated safely."""


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
    skills = package["skills"]
    if not isinstance(skills, list) or not all(isinstance(item, Mapping) for item in skills):
        raise PackageError("skills deve ser uma lista de objetos")
    copied = {key: value for key, value in package.items()}
    return copied


def package_capability(package: Mapping[str, Any], name: str) -> str:
    entry = package.get("capabilities", {}).get(name, {})
    state = str(entry.get("state", "disabled"))
    if package.get("lifecycle", "active") == "draft" and state in {"enabled", "assisted"}:
        return "pending"
    return state
