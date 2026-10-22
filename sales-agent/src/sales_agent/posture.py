"""Owner-approved sales posture for inbound conversations.

The owner chooses how much initiative the seller takes (``answer``,
``suggest`` or ``lead``); the buyer's state always wins. This module decides
deterministically whether an opportunity moment may carry one extra move
(a complement from the package or an offer to prepare the order) and keeps
the per-conversation budget. The model never chooses a move.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

from .drafting import brl

INITIATIVES = ("answer", "suggest", "lead")
MAX_SUGGESTIONS = 3
MAX_PITCH_CHARS = 200
MAX_REMINDERS = 2
# WhatsApp accepts free-form messages only within 24 h of the buyer's last
# message; reminders must land well inside that window.
REMINDER_WINDOW_MINUTES = 23 * 60
QUIET_START_HOUR = 21
QUIET_END_HOUR = 9
DEFAULT_REMINDER_TEXTS = (
    "Oi! Seu pedido de {produto} ficou em aberto. Se ainda quiser, é só me responder que eu sigo com você.",
    "Passando só para lembrar do seu pedido de {produto}. Se não for mais o caso, tudo bem, não te chamo de novo.",
)

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
        "abandoned_checkout_reminders": int(posture.get(
            "abandoned_checkout_reminders", {"answer": 0, "suggest": 1, "lead": 2}.get(initiative, 0))),
        "reminder_after_minutes": int(posture.get("reminder_after_minutes", 180)),
        "reminder_texts": [str(item) for item in posture.get("reminder_texts", [])],
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
    allowed = {"initiative", "cross_sell", "ask_for_close", "alternative_on_objection", "max_suggestions_per_conversation",
               "abandoned_checkout_reminders", "reminder_after_minutes", "reminder_texts"}
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
    reminders = posture.get("abandoned_checkout_reminders", 0)
    if isinstance(reminders, bool) or not isinstance(reminders, int) or not 0 <= reminders <= MAX_REMINDERS:
        raise ValueError("sales_posture.abandoned_checkout_reminders deve ser inteiro entre 0 e %d" % MAX_REMINDERS)
    after = posture.get("reminder_after_minutes", 180)
    if isinstance(after, bool) or not isinstance(after, int) or after < 15 or after * max(reminders, 1) > REMINDER_WINDOW_MINUTES:
        raise ValueError("sales_posture.reminder_after_minutes deve ser ao menos 15 e caber nas 23 h da janela")
    texts = posture.get("reminder_texts", [])
    if not isinstance(texts, list) or len(texts) > MAX_REMINDERS or not all(
        isinstance(item, str) and item.strip() and len(item) <= 300 and "http" not in item.casefold() for item in texts
    ):
        raise ValueError("sales_posture.reminder_texts deve ter até %d textos curtos, sem links" % MAX_REMINDERS)
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


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _business_timezone(package: Mapping[str, Any]) -> ZoneInfo:
    hours = package.get("service_hours") if isinstance(package.get("service_hours"), Mapping) else {}
    settings = package.get("settings") if isinstance(package.get("settings"), Mapping) else {}
    try:
        return ZoneInfo(str(hours.get("timezone") or settings.get("timezone") or "America/Sao_Paulo"))
    except Exception:
        return ZoneInfo("America/Sao_Paulo")


def _outside_quiet_hours(moment: datetime, zone: ZoneInfo) -> datetime:
    local = moment.astimezone(zone)
    if QUIET_END_HOUR <= local.hour < QUIET_START_HOUR:
        return moment
    morning = local.replace(hour=QUIET_END_HOUR, minute=0, second=0, microsecond=0)
    if local.hour >= QUIET_START_HOUR:
        morning += timedelta(days=1)
    return morning.astimezone(moment.tzinfo)


def plan_checkout_reminders(
    package: Mapping[str, Any], state: Mapping[str, Any], offer: Mapping[str, Any], now: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return (reminders, reason_if_none) for a checkout link prepared ``now``.

    The buyer just wrote, so the 24 h window starts at ``now``. A reminder
    that would fall in quiet hours moves to the morning; one that would then
    leave the window is dropped instead of being sent late.
    """
    settings = posture_settings(package)
    count = settings["abandoned_checkout_reminders"] if settings["initiative"] != "answer" else 0
    if count <= 0:
        return [], None
    capability = package.get("capabilities", {}).get("follow_up", {})
    if not isinstance(capability, Mapping) or capability.get("state") not in {"enabled", "assisted"}:
        return [], "follow_up_capability_disabled"
    memory = state.get("posture") if isinstance(state.get("posture"), Mapping) else {}
    if memory.get("declined") or not state.get("follow_up_allowed", True):
        return [], "buyer_declined"
    start = _parse(now)
    deadline = start + timedelta(minutes=REMINDER_WINDOW_MINUTES)
    zone = _business_timezone(package)
    texts = settings["reminder_texts"] or list(DEFAULT_REMINDER_TEXTS)
    reminders = []
    for number in range(1, count + 1):
        due = _outside_quiet_hours(start + timedelta(minutes=settings["reminder_after_minutes"] * number), zone)
        if due > deadline or (reminders and due <= _parse(reminders[-1]["available_at"])):
            break
        text = texts[min(number, len(texts)) - 1].replace("{produto}", str(offer.get("name", "seu pedido")))
        reminders.append({"number": number, "available_at": due.isoformat(timespec="seconds"), "text": text})
    return reminders, None if reminders else "window_would_close"


def reminder_still_valid(state: Mapping[str, Any], package: Mapping[str, Any], item: Mapping[str, Any], now: str) -> Tuple[bool, str]:
    """Recheck an abandoned-checkout reminder immediately before delivery."""
    operation = state.get("operation") if isinstance(state.get("operation"), Mapping) else {}
    if state.get("last_event_id") != item.get("after_event_id"):
        return False, "buyer_replied"
    if operation.get("type") != "checkout" or operation.get("checkout_id") != item.get("checkout_id"):
        return False, "checkout_changed"
    if operation.get("payment_status") or operation.get("status") != "confirmed":
        return False, "payment_in_progress"
    if not state.get("follow_up_allowed", True) or (state.get("posture") or {}).get("declined"):
        return False, "buyer_declined"
    settings = posture_settings(package)
    if settings["initiative"] == "answer" or int(item.get("number", 1)) > settings["abandoned_checkout_reminders"]:
        return False, "posture_changed"
    capability = package.get("capabilities", {}).get("follow_up", {})
    if not isinstance(capability, Mapping) or capability.get("state") not in {"enabled", "assisted"}:
        return False, "capability_changed"
    moment = _parse(now)
    if _outside_quiet_hours(moment, _business_timezone(package)) != moment:
        return False, "quiet_hours"
    if moment - _parse(str(item.get("window_started_at"))) > timedelta(minutes=REMINDER_WINDOW_MINUTES):
        return False, "reminder_window_closed"
    return True, "eligible"
