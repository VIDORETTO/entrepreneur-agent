"""Validation for business packages and persisted configuration."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping


class PackageError(ValueError):
    """A business package cannot be activated safely."""


CAPABILITY_STATES = {"enabled", "assisted", "disabled", "pending"}
OFFER_KINDS = {"physical", "digital", "service"}
MODES = {"direct", "consultative", "proposal", "appointment"}


def _require(value: Any, path: str) -> None:
    if value is None or value == "":
        raise PackageError("campo obrigatório ausente: %s" % path)


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
    if not isinstance(business["buyer_types"], list) or not business["buyer_types"]:
        raise PackageError("business.buyer_types deve ser uma lista não vazia")
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
            _require(offer.get("price"), "%s.price" % path)
        if not isinstance(offer.get("required_fields", []), list):
            raise PackageError("%s.required_fields deve ser uma lista" % path)
        if offer["kind"] == "physical" and not isinstance(offer.get("stock", {}), Mapping):
            raise PackageError("%s.stock deve ser um objeto" % path)
    capabilities = package["capabilities"]
    if not isinstance(capabilities, Mapping):
        raise PackageError("capabilities deve ser um objeto")
    for name, entry in capabilities.items():
        if not isinstance(entry, Mapping) or entry.get("state") not in CAPABILITY_STATES:
            raise PackageError("capability %s precisa de state válido" % name)
        if entry["state"] in {"disabled", "pending"} and not entry.get("reason"):
            raise PackageError("capability %s precisa explicar sua lacuna" % name)
    sources = package["sources"]
    if not isinstance(sources, list):
        raise PackageError("sources deve ser uma lista")
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise PackageError("sources[%d] deve ser um objeto" % index)
        for field in ("id", "version", "status", "content"):
            _require(source.get(field), "sources[%d].%s" % (index, field))
        if source["status"] not in {"approved", "revoked", "pending"}:
            raise PackageError("status de fonte inválido")
        if source["status"] == "approved" and not source.get("origin"):
            raise PackageError("fonte aprovada precisa de origin")
    skills = package["skills"]
    if not isinstance(skills, list) or not all(isinstance(item, Mapping) for item in skills):
        raise PackageError("skills deve ser uma lista de objetos")
    copied = {key: value for key, value in package.items()}
    return copied


def package_capability(package: Mapping[str, Any], name: str) -> str:
    entry = package.get("capabilities", {}).get(name, {})
    return str(entry.get("state", "disabled"))
