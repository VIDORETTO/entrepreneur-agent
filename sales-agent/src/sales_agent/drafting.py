"""Deterministic boundary for optional buyer-facing response drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


def _money(text: str) -> set[str]:
    amounts = set()
    for match in re.finditer(r"R\$\s*(\d+(?:[.,]\d{1,2})?)", text, re.I):
        amounts.add("%.2f" % float(match.group(1).replace(",", ".")))
    return amounts


def _percents(text: str) -> set[str]:
    return {match.group(1).replace(",", ".") for match in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*%", text)}


def _urls(text: str) -> set[str]:
    return {match.group(0).rstrip(".,;)") for match in re.finditer(r"https?://[^\s<>]+", text, re.I)}


def _durations(text: str) -> set[str]:
    units = {"dia": "day", "dias": "day", "mês": "month", "mes": "month", "meses": "month",
             "hora": "hour", "horas": "hour", "semana": "week", "semanas": "week", "ano": "year", "anos": "year"}
    return {"%s %s" % (match.group(1), units[match.group(2).casefold()])
            for match in re.finditer(r"\b(\d+)\s*(dias?|mês|meses|mes|horas?|semanas?|anos?)\b", text, re.I)}


def _quantities(text: str) -> set[str]:
    units = {"unidade": "unit", "unidades": "unit", "licença": "license", "licenças": "license",
             "licenca": "license", "licencas": "license", "item": "item", "itens": "item",
             "peça": "piece", "peças": "piece", "peca": "piece", "pecas": "piece"}
    return {"%s %s" % (match.group(1), units[match.group(2).casefold()])
            for match in re.finditer(r"\b(\d+)\s*(unidades?|licen[çc]as?|itens?|pe[çc]as?)\b", text, re.I)}


def policy_claims(text: str) -> list[tuple[str, str]]:
    """Extract explicit policy polarity for the supervisor and draft gate."""
    value = text.casefold()
    patterns = {
        "guarantee": (
            r"garant(?:ia|ias)",
            r"(?:não|nao)\s+(?:cobre|inclui|abrange|oferece)|sem\s+garantia",
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
    }
    claims: list[tuple[str, str]] = []
    for subject, (keyword, negative_pattern, positive_pattern) in patterns.items():
        if not re.search(keyword, value):
            continue
        negative = bool(re.search(negative_pattern, value))
        positive = bool(re.search(positive_pattern, value)) and not negative
        if negative:
            claims.append((subject, "negative"))
        elif positive:
            claims.append((subject, "positive"))
    return claims


def commercial_claims(text: str) -> list[tuple[str, str]]:
    """Conservative claims recognized by both draft and supervisor gates."""
    value = text.casefold()
    claims = []
    for match in re.finditer(r"(?:r\$\s*|\b)([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:reais?|rs\.?|r\$)?", value):
        amount = re.sub(r"[^0-9]", "", match.group(1))
        if match.group(0).strip().lower().endswith(("reais", "real", "rs", "r$")) or "r$" in match.group(0).lower():
            claims.append(("price", amount))
    for match in re.finditer(r"\b(\d+)\s*(dias?|meses?|semanas?)\b", value):
        unit = match.group(2)
        if unit.startswith("dia"):
            unit = "dias"
        elif unit.startswith("mes"):
            unit = "meses"
        else:
            unit = "semanas"
        claims.append(("deadline", "%s %s" % (match.group(1), unit)))
    patterns = {
        "payment_status": (r"pagamento\s+(?:foi\s+)?confirmado", "payment_confirmed"),
        "shipping": (r"frete\s+(?:é\s+)?gr[aá]tis", "free_shipping"),
        "guarantee_duration": (r"garantia\s+(?:é\s+)?vital[ií]cia", "lifetime_guarantee"),
        "delivery_tomorrow": (r"entreg(?:a|amos)\s+amanh[ãa]", "delivery_tomorrow"),
        "discount": (r"\bdesconto\b", "discount"),
        "refund": (r"\bestorno\b|\breembolso\b", "refund"),
    }
    for kind, (pattern, value_name) in patterns.items():
        if re.search(pattern, value):
            claims.append((kind, value_name))
    return claims


@dataclass(frozen=True)
class ResponseRequirements:
    buyer_text: str
    template: str
    evidence: tuple[str, ...]
    allowed_prices: frozenset[str]
    allowed_percents: frozenset[str]
    allowed_urls: frozenset[str]
    allowed_durations: frozenset[str]
    allowed_quantities: frozenset[str]
    allowed_commercial_claims: frozenset[tuple[str, str]]
    allowed_policy_claims: frozenset[tuple[str, str]]
    checkout_url: str | None
    question_field: str | None
    topics: tuple[str, ...]

    @classmethod
    def from_result(cls, buyer_text: str, result: Any) -> "ResponseRequirements":
        evidence = tuple(str(item.get("content", "")) for item in result.evidence if isinstance(item, Mapping))
        allowed_prices = set(_money(result.response))
        for content in evidence:
            allowed_prices.update(_money(content))
        allowed_percents = set(_percents(result.response))
        for content in evidence:
            allowed_percents.update(_percents(content))
        allowed_urls = set(_urls(result.response))
        allowed_durations = set(_durations(result.response))
        allowed_quantities = set(_quantities(result.response))
        for content in evidence:
            allowed_urls.update(_urls(content))
            allowed_durations.update(_durations(content))
            allowed_quantities.update(_quantities(content))
        trusted_texts = (result.response, *evidence)
        allowed_commercial_claims = frozenset(claim for text in trusted_texts for claim in commercial_claims(text))
        allowed_policy_claims = frozenset(claim for text in trusted_texts for claim in policy_claims(text))
        pending = result.state.get("pending")
        question_field = str(pending.get("field")) if isinstance(pending, Mapping) and pending.get("field") else None
        action = result.action or {}
        checkout_url = str(action.get("url")) if action.get("type") == "prepare_checkout" and action.get("url") else None
        topics = tuple(topic for topic, pattern in {
            "price": r"pre[çc]o|custa|valor|R\$",
            "access": r"acesso|libera[çc][ãa]o",
            "delivery": r"entrega|frete|prazo|chegar",
            "duration": r"por quanto tempo|dura[çc][ãa]o|\bdura\b",
        }.items() if re.search(pattern, buyer_text, re.I))
        return cls(buyer_text, result.response, evidence, frozenset(allowed_prices), frozenset(allowed_percents), frozenset(allowed_urls),
                   frozenset(allowed_durations), frozenset(allowed_quantities),
                   allowed_commercial_claims, allowed_policy_claims,
                   checkout_url, question_field, topics)


class ClaimVerifier:
    """Check draft claims against observed, trusted data before delivery."""

    @staticmethod
    def verify(draft: str, requirements: ResponseRequirements) -> list[dict[str, str]]:
        violations: list[dict[str, str]] = []
        for price in sorted(_money(draft) - requirements.allowed_prices):
            violations.append({"kind": "price", "value": price})
        for percent in sorted(_percents(draft) - requirements.allowed_percents):
            violations.append({"kind": "percentage", "value": percent})
        observed_urls = _urls(draft)
        for url in sorted(observed_urls - requirements.allowed_urls):
            violations.append({"kind": "url", "value": url})
        if requirements.checkout_url and requirements.checkout_url not in observed_urls:
            violations.append({"kind": "required_url", "value": requirements.checkout_url})
        for duration in sorted(_durations(draft) - requirements.allowed_durations):
            violations.append({"kind": "deadline", "value": duration})
        for quantity in sorted(_quantities(draft) - requirements.allowed_quantities):
            violations.append({"kind": "quantity", "value": quantity})
        for kind, value in sorted(set(commercial_claims(draft)) - requirements.allowed_commercial_claims):
            violations.append({"kind": kind, "value": value})
        for subject, polarity in sorted(set(policy_claims(draft)) - requirements.allowed_policy_claims):
            violations.append({"kind": "policy", "value": "%s:%s" % (subject, polarity)})
        if requirements.question_field:
            terms = {
                "variant": r"tamanho|variante",
                "quantity": r"quantidade|quantas?|unidades?",
                "region": r"regi[ãa]o|cidade|estado|cep|entrega",
                "email": r"e-?mail|contato",
                "scope": r"escopo|servi[çc]o|precisa",
            }.get(requirements.question_field, re.escape(requirements.question_field))
            if "?" not in draft or not re.search(terms, draft, re.I):
                violations.append({"kind": "necessary_question", "value": requirements.question_field})
        topic_terms = {
            "price": r"R\$|pre[çc]o|custa|valor",
            "access": r"acesso|libera[çc][ãa]o",
            "delivery": r"entrega|frete|prazo|chegar",
            "duration": r"dura[çc][ãa]o|\d+\s*(?:dias?|meses?|horas?|anos?)|\btempo\b",
        }
        for topic in requirements.topics:
            if not re.search(topic_terms[topic], draft, re.I):
                violations.append({"kind": "topic_missing", "value": topic})
        return violations
