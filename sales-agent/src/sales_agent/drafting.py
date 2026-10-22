"""Deterministic boundary for optional buyer-facing response drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .voice import buyer_register, select_examples, style_violations, voice_settings


def injection_signals(text: str) -> list[str]:
    """Return lexical signals for audit; policy stays with the engine."""
    patterns = {
        "override": r"\bignore\b.{0,80}\b(?:instru[çc][õo]es|regras|prompt)\b|\bconcorde\s+com\s+tudo\b",
        "contract": r"juridicamente\s+vinculante|\b(?:aceite|aceito)\s+(?:este|o)\s+contrato\b",
        "role": r"\b(?:assistente|sistema|system|developer)\s*:\s*(?:ofere[çc]a|ignore|revele|mostre)",
        "exfiltration": r"(?:mostre|revele|imprima).{0,50}\b(?:prompt|instru[çc][õo]es|skills?)\b",
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text, re.I | re.S)]


_NUMBER_WORDS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "catorze": 14, "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200,
    "duzentas": 200, "trezentos": 300, "trezentas": 300, "quatrocentos": 400, "quatrocentas": 400,
    "quinhentos": 500, "quinhentas": 500, "seiscentos": 600, "seiscentas": 600, "setecentos": 700,
    "setecentas": 700, "oitocentos": 800, "oitocentas": 800, "novecentos": 900, "novecentas": 900,
}
_WORD = r"(?:%s)" % "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True))
# "mil" is a multiplier; "um" may be omitted before it ("mil e duzentos").
_SPELLED = r"(?:(?:%s|mil)(?:\s+(?:e\s+)?(?:%s|mil))*)" % (_WORD, _WORD)
_NUMBER = r"(\d+|%s)" % _SPELLED


def _spelled_value(words: str) -> int | None:
    total = 0
    current = 0
    for token in re.findall(r"[a-zà-ú]+", words.casefold()):
        if token == "e":
            continue
        if token == "mil":
            total += (current or 1) * 1000
            current = 0
        elif token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
        else:
            return None
    return total + current


def _number_value(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else _spelled_value(raw)


def parse_amount(raw: str) -> str | None:
    """Canonicalize a written amount ("1.299,90", "79.90", "79") to "1299.90"."""
    value = raw.strip().rstrip(".,")
    if not value or not re.fullmatch(r"\d[\d.,]*", value):
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        whole, _, decimals = value.rpartition(",")
        value = "%s.%s" % (whole.replace(",", ""), decimals) if len(decimals) in {1, 2} else value.replace(",", "")
    elif "." in value:
        whole, _, decimals = value.rpartition(".")
        value = "%s.%s" % (whole.replace(".", ""), decimals) if len(decimals) in {1, 2} else value.replace(".", "")
    try:
        return "%.2f" % float(value)
    except ValueError:
        return None


def brl(amount: float) -> str:
    """Format money the way a Brazilian buyer reads it: R$ 1.299,90."""
    whole, cents = ("%.2f" % float(amount)).split(".")
    return "R$ %s,%s" % ("{:,}".format(int(whole)).replace(",", "."), cents)


def _money(text: str) -> set[str]:
    amounts = set()
    for match in re.finditer(r"R\$\s*(\d[\d.,]*)", text, re.I):
        amount = parse_amount(match.group(1))
        if amount:
            amounts.add(amount)
    for match in re.finditer(r"(?<![\w$])(\d[\d.,]*)\s*(?:reais|real)\b", text, re.I):
        amount = parse_amount(match.group(1))
        if amount:
            amounts.add(amount)
    spelled = r"\b(%s)\s+(?:reais|real)\b(?:\s+e\s+(%s)\s+centavos?)?" % (_SPELLED, _SPELLED)
    for match in re.finditer(spelled, text, re.I):
        whole = _spelled_value(match.group(1))
        cents = _spelled_value(match.group(2)) if match.group(2) else 0
        if whole is not None and cents is not None and cents < 100:
            amounts.add("%d.%02d" % (whole, cents))
    return amounts


def _percents(text: str) -> set[str]:
    return {match.group(1).replace(",", ".") for match in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(?:%|por\s*cento)", text, re.I)}


def _urls(text: str) -> set[str]:
    return {match.group(0).rstrip(".,;)") for match in re.finditer(r"https?://[^\s<>]+", text, re.I)}


_DURATION_UNITS = {"dia": "day", "dias": "day", "mês": "month", "mes": "month", "meses": "month",
                   "hora": "hour", "horas": "hour", "semana": "week", "semanas": "week", "ano": "year", "anos": "year"}


def _durations(text: str) -> set[str]:
    found = set()
    for match in re.finditer(r"\b%s\s*(dias?|mês|meses|mes|horas?|semanas?|anos?)\b" % _NUMBER, text, re.I):
        value = _number_value(match.group(1).casefold())
        if value is not None:
            found.add("%s %s" % (value, _DURATION_UNITS[match.group(2).casefold()]))
    return found


def _quantities(text: str) -> set[str]:
    units = {"unidade": "unit", "unidades": "unit", "licença": "license", "licenças": "license",
             "licenca": "license", "licencas": "license", "item": "item", "itens": "item",
             "peça": "piece", "peças": "piece", "peca": "piece", "pecas": "piece"}
    found = set()
    for match in re.finditer(r"\b%s\s*(unidades?|licen[çc]as?|itens?|item|pe[çc]as?)\b" % _NUMBER, text, re.I):
        value = _number_value(match.group(1).casefold())
        if value is not None:
            found.add("%s %s" % (value, units[match.group(2).casefold()]))
    return found


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
    claims = [("price", amount) for amount in sorted(_money(text))]
    for match in re.finditer(r"\b%s\s*(dias?|meses?|m[eê]s|semanas?)\b" % _NUMBER, value):
        amount = _number_value(match.group(1))
        if amount is None:
            continue
        unit = match.group(2)
        if unit.startswith("dia"):
            unit = "dias"
        elif unit.startswith("m"):
            unit = "meses"
        else:
            unit = "semanas"
        claims.append(("deadline", "%s %s" % (amount, unit)))
    patterns = {
        "payment_status": (r"pagamento\s+(?:j[aá]\s+)?(?:foi\s+)?(?:confirmado|aprovado|compensado)|j[aá]\s+caiu\s+(?:o\s+)?(?:pix|pagamento)", "payment_confirmed"),
        "shipping": (r"frete\s+(?:[ée]\s+|sai\s+|fica\s+|vai\s+(?:sair\s+)?)?(?:gr[aá]tis|gratuito|de\s+gra[çc]a|zero|free|por\s+nossa\s+conta)"
                     r"|sem\s+(?:custo|cobran[çc]a|taxa)\s+de\s+(?:frete|entrega)|n[ãa]o\s+(?:paga|cobra(?:mos)?)\s+(?:o\s+)?frete"
                     r"|entrega\s+(?:[ée]\s+)?(?:gr[aá]tis|gratuita)", "free_shipping"),
        "guarantee_duration": (r"garantia\s+(?:[ée]\s+)?(?:vital[ií]cia|eterna|para\s+sempre)", "lifetime_guarantee"),
        "delivery_tomorrow": (r"(?:entreg|cheg)\w*\s+(?:j[aá]\s+)?amanh[ãa]|amanh[ãa]\s+(?:mesmo\s+)?(?:j[aá]\s+)?(?:est[aá]\s+a[ií]|chega)", "delivery_tomorrow"),
        "discount": (r"\bdesconto\b|\babatimento\b|\bpromo[çc][ãa]o\b|\b\d+\s*%\s*off\b", "discount"),
        "refund": (r"\bestorno\b|\breembolso\b|devolvemos\s+(?:o\s+)?(?:seu\s+)?dinheiro", "refund"),
    }
    for kind, (pattern, value_name) in patterns.items():
        if re.search(pattern, value):
            claims.append((kind, value_name))
    return claims


# The buyer may ask whether they are talking to a person; the seller never
# claims to be one (transparency rules such as EU AI Act art. 50).
HUMAN_CLAIM_PATTERN = (
    r"\bsou\s+(?:uma?\s+)?(?:pessoa(?:\s+de\s+verdade|\s+real)?|humana?|gente\s+de\s+verdade|atendente\s+(?:real|de\s+verdade|humana?))\b"
    r"|\bn[ãa]o\s+sou\s+(?:um\s+|uma\s+)?(?:rob[ôo]|bot|ia\b|intelig[êe]ncia\s+artificial|assistente\s+virtual|m[áa]quina)"
)


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
    history: tuple[Mapping[str, str], ...] = ()
    voice: Mapping[str, Any] | None = None
    examples: tuple[Mapping[str, str], ...] = ()
    register: Mapping[str, Any] | None = None

    @classmethod
    def from_result(
        cls,
        buyer_text: str,
        result: Any,
        *,
        history: Sequence[Mapping[str, str]] = (),
        voice: Optional[Mapping[str, Any]] = None,
    ) -> "ResponseRequirements":
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
        voice = dict(voice) if voice is not None else voice_settings({})
        history = tuple(dict(item) for item in history)
        examples = tuple(select_examples(voice, buyer_text))
        register = buyer_register([str(item.get("buyer", "")) for item in history] + [buyer_text])
        return cls(buyer_text, result.response, evidence, frozenset(allowed_prices), frozenset(allowed_percents), frozenset(allowed_urls),
                   frozenset(allowed_durations), frozenset(allowed_quantities),
                   allowed_commercial_claims, allowed_policy_claims,
                   checkout_url, question_field, topics, history, voice, examples, register)


class ClaimVerifier:
    """Check draft claims against observed, trusted data before delivery."""

    @staticmethod
    def verify(draft: str, requirements: ResponseRequirements) -> list[dict[str, str]]:
        violations: list[dict[str, str]] = []
        forbidden_patterns = {
            "claims_human": HUMAN_CLAIM_PATTERN,
            "internal_instruction": r"\b(?:seller-conversation|sales-setup|sales-business-discovery|system\s*:|developer\s*:|system prompt)\b",
            "contract_acceptance": r"juridicamente\s+vinculante|\b(?:aceito|aceitamos|concordo|concordamos)\b.{0,40}\b(?:contrato|condi[çc][õo]es|termos)\b",
        }
        for kind, pattern in forbidden_patterns.items():
            if re.search(pattern, draft, re.I):
                violations.append({"kind": kind, "value": "prohibited_content"})
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
        violations.extend(style_violations(
            draft,
            requirements.voice or voice_settings({}),
            template=requirements.template,
            question_field=requirements.question_field,
            previous_seller=[str(item.get("seller", "")) for item in requirements.history],
        ))
        return violations
