"""Owner-approved sales posture for inbound conversations.

The owner chooses how much initiative the seller takes (``answer``,
``suggest`` or ``lead``); the buyer's state always wins. This module decides
deterministically whether an opportunity moment may carry one extra move
(a complement from the package or an offer to prepare the order) and keeps
the per-conversation budget. The model never chooses a move.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from .drafting import brl

INITIATIVES = ("answer", "suggest", "lead")
MAX_SUGGESTIONS = 3
MAX_PITCH_CHARS = 200

# Short replies to "quer que eu já prepare o seu pedido?".
AFFIRMATIVE = re.compile(
    r"^\s*(?:sim|s|quero|pode(?:\s+sim)?|bora|claro|manda|isso|fechado|separa|prepara|por favor|ok|beleza|blz)\b",
    re.I,
)
NEGATIVE = re.compile(
    r"^\s*(?:n[ãa]o|nao|agora\s+n[ãa]o|ainda\s+n[ãa]o|depois|s[óo]\s+(?:olhando|pesquisando|vendo)|deixa\s+(?:pra|para)\s+depois)\b",
    re.I,
)

# Scenario answers from the owner interview: "A" only answers, "B" suggests a
# complement, "C" offers to prepare the order.
_INTERVIEW_CHOICES = (
    ("lead", r"^\s*c\b|conduz|j[áa] separ|separar|prepar|fechar|fechamento|ativ[ao]"),
    ("suggest", r"^\s*b\b|suger|complement|combina|oferec|indic"),
    ("answer", r"^\s*a\b|s[óo] (?:o )?pre[çc]o|s[óo] respond|apenas respond|respond(?:er)? s[óo]|passiv"),
)

POSTURE_QUESTION = {
    "id": "posture",
    "prompt": (
        "Um cliente pergunta o preço de um produto. Qual resposta parece a sua loja? "
        "(A) só o preço; (B) o preço e uma sugestão de complemento, como \"temos a meia combinando\"; "
        "(C) o preço e \"quer que eu já separe o seu?\"."
    ),
    "impact": "define quanta iniciativa a IA toma quando o cliente chega; sem resposta, ela só responde",
    "optional": True,
}


def posture_settings(package: Mapping[str, Any]) -> Dict[str, Any]:
    posture = package.get("sales_posture") if isinstance(package.get("sales_posture"), Mapping) else {}
    initiative = str(posture.get("initiative") or "answer")
    return {
        "initiative": initiative,
        "cross_sell": [dict(item) for item in posture.get("cross_sell", []) if isinstance(item, Mapping)],
        "ask_for_close": bool(posture.get("ask_for_close", initiative == "lead")),
        "alternative_on_objection": bool(posture.get("alternative_on_objection", True)),
        "max_suggestions_per_conversation": int(posture.get("max_suggestions_per_conversation", 1)),
    }


def initiative_from_answer(answer: str) -> Optional[str]:
    value = answer.casefold()
    for initiative, pattern in _INTERVIEW_CHOICES:
        if re.search(pattern, value):
            return initiative
    return None


def validate_posture(posture: Any, offer_ids: List[str]) -> None:
    """Raise ValueError when a posture cannot be applied safely."""
    if posture is None:
        return
    if not isinstance(posture, Mapping):
        raise ValueError("sales_posture deve ser um objeto")
    allowed = {"initiative", "cross_sell", "ask_for_close", "alternative_on_objection", "max_suggestions_per_conversation"}
    unknown = sorted(set(posture) - allowed)
    if unknown:
        raise ValueError("sales_posture tem chaves desconhecidas: %s" % ", ".join(unknown))
    if posture.get("initiative", "answer") not in INITIATIVES:
        raise ValueError("sales_posture.initiative deve ser answer, suggest ou lead")
    for key in ("ask_for_close", "alternative_on_objection"):
        if key in posture and not isinstance(posture[key], bool):
            raise ValueError("sales_posture.%s deve ser booleano" % key)
    limit = posture.get("max_suggestions_per_conversation", 1)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= MAX_SUGGESTIONS:
        raise ValueError("sales_posture.max_suggestions_per_conversation deve ser inteiro entre 0 e %d" % MAX_SUGGESTIONS)
    rules = posture.get("cross_sell", [])
    if not isinstance(rules, list):
        raise ValueError("sales_posture.cross_sell deve ser uma lista")
    for index, rule in enumerate(rules):
        path = "sales_posture.cross_sell[%d]" % index
        if not isinstance(rule, Mapping) or set(rule) - {"when_offer", "suggest", "pitch"}:
            raise ValueError("%s aceita apenas when_offer, suggest e pitch" % path)
        if rule.get("when_offer") not in offer_ids or rule.get("suggest") not in offer_ids:
            raise ValueError("%s precisa citar ofertas do pacote" % path)
        if rule["when_offer"] == rule["suggest"]:
            raise ValueError("%s não pode sugerir a própria oferta" % path)
        pitch = rule.get("pitch")
        if pitch is not None and (not isinstance(pitch, str) or not pitch.strip() or len(pitch) > MAX_PITCH_CHARS):
            raise ValueError("%s.pitch deve ser texto de até %d caracteres" % (path, MAX_PITCH_CHARS))


def _available(offer: Mapping[str, Any]) -> bool:
    stock = offer.get("stock")
    if isinstance(stock, Mapping) and stock:
        return any(isinstance(value, int) and value > 0 for value in stock.values())
    return True


def _cross_sell_text(rule: Mapping[str, Any], target: Mapping[str, Any]) -> str:
    if rule.get("pitch"):
        return str(rule["pitch"]).strip()
    if target.get("price_type", "fixed") == "fixed" and target.get("price") is not None:
        suffix = " a unidade" if target.get("kind") == "physical" else ""
        return "Se quiser, também temos %s por %s%s." % (target["name"], brl(float(target["price"])), suffix)
    return "Se quiser, também temos %s." % target["name"]


def plan_move(
    package: Mapping[str, Any],
    state: Mapping[str, Any],
    moment: str,
    offer: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return at most one move for an opportunity moment, or None.

    ``moment`` is ``price`` (a fixed price was just answered) or ``checkout``
    (the buyer's order link was just prepared).
    """
    settings = posture_settings(package)
    if settings["initiative"] == "answer" or not offer:
        return None
    if str(state.get("profile", "commercial")) != "commercial" or state.get("status") not in {None, "active"}:
        return None
    memory = state.get("posture") if isinstance(state.get("posture"), Mapping) else {}
    if memory.get("declined"):
        return None
    if int(memory.get("suggestions", 0)) >= settings["max_suggestions_per_conversation"]:
        return None
    history_length = len(state.get("history", []) or [])
    if memory.get("last_move_turn") is not None and history_length - int(memory["last_move_turn"]) <= 1:
        return None
    if moment == "price" and settings["initiative"] == "lead" and settings["ask_for_close"]:
        return {"move": "ask_for_close", "offer_id": offer["id"], "text": "Quer que eu já prepare o seu pedido?"}
    if moment in {"price", "checkout"}:
        offers = {str(item.get("id")): item for item in package.get("offers", []) if isinstance(item, Mapping)}
        for rule in settings["cross_sell"]:
            target = offers.get(str(rule.get("suggest")))
            if rule.get("when_offer") == offer.get("id") and target and _available(target):
                return {"move": "cross_sell", "offer_id": target["id"], "text": _cross_sell_text(rule, target)}
    return None


def record_move(state: Dict[str, Any], move: Mapping[str, Any]) -> None:
    memory = state.setdefault("posture", {})
    memory["suggestions"] = int(memory.get("suggestions", 0)) + 1
    memory["last_move_turn"] = len(state.get("history", []) or [])
    if move["move"] == "ask_for_close":
        memory["open_close_offer"] = move["offer_id"]


def record_decline(state: Dict[str, Any]) -> None:
    memory = state.setdefault("posture", {})
    memory["declined"] = True
    memory.pop("open_close_offer", None)
