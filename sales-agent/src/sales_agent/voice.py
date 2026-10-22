"""Owner-approved voice for buyer-facing text.

The engine decides *what* is said; this module only shapes *how* it sounds:
voice settings from the package, a deterministic lint for phrasing that reads
as machine-written, the buyer's register and the owner examples closest to
the current turn. Nothing here may add a commercial fact.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Sequence

EMOJI_POLICIES = {"none", "light", "free"}
ADDRESS_FORMS = {"você", "tu"}
MAX_EXAMPLES = 60
MAX_EXAMPLE_CHARS = 600

# Openers, fillers and closers that buyers recognize as bot copy. They are
# style problems, not safety problems: a draft that uses them is retried and,
# if it still does, the engine keeps its own template.
DEFAULT_FORBIDDEN_PHRASES = (
    r"[óo]tima pergunta",
    r"excelente pergunta",
    r"boa pergunta",
    r"fico feliz em (?:te )?(?:ajudar|saber|poder)",
    r"como posso (?:te |lhe )?ajudar",
    r"em que posso (?:te |lhe )?ajudar",
    r"posso (?:te )?ajudar em (?:algo|mais alguma)",
    r"mais alguma coisa",
    r"estou (?:aqui )?(?:à|a) disposi[çc][ãa]o",
    r"estou aqui para (?:te )?ajudar",
    r"espero ter (?:te )?ajudado",
    r"n[ãa]o hesite",
    r"sinta-se (?:à|a) vontade",
    r"entendo (?:a sua|sua|a) preocupa[çc][ãa]o",
    r"compreendo (?:perfeitamente|totalmente)",
    r"como (?:um |uma )?(?:assistente virtual|ia|intelig[êe]ncia artificial),",
    r"prezad[oa]",
    r"caro cliente",
    r"agradecemos (?:o seu|seu) contato",
    r"[ée] um prazer (?:te |lhe )?(?:atender|ajudar)",
    r"\bcertamente\b",
)

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B50\U00002705]"
)


def voice_settings(package: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the package voice with defaults for every optional key."""
    voice = package.get("voice") if isinstance(package.get("voice"), Mapping) else {}
    return {
        "assistant_name": str(voice.get("assistant_name") or "").strip() or None,
        "disclose_ai": bool(voice.get("disclose_ai", True)),
        "tone": str(voice.get("tone") or "").strip(),
        "address": str(voice.get("address") or "você"),
        "emoji": str(voice.get("emoji") or "light"),
        "max_chars": int(voice.get("max_chars") or 320),
        "forbidden_phrases": [str(item) for item in voice.get("forbidden_phrases", []) if str(item).strip()],
        "examples": [dict(item) for item in voice.get("examples", []) if isinstance(item, Mapping)],
    }


def introduction(package: Mapping[str, Any]) -> str:
    """Opening line that tells the buyer they are talking to an assistant."""
    voice = voice_settings(package)
    business = str(package.get("business", {}).get("name", "")).strip()
    if not voice["disclose_ai"]:
        return "Oi! Aqui é da %s." % business if business else "Oi!"
    if voice["assistant_name"]:
        return "Oi! Aqui é %s, assistente virtual da %s." % (voice["assistant_name"], business)
    return "Oi! Aqui é o atendimento virtual da %s." % business


def ai_disclosure(package: Mapping[str, Any]) -> str:
    voice = voice_settings(package)
    business = str(package.get("business", {}).get("name", "")).strip()
    if voice["assistant_name"]:
        return "Sou %s, assistente virtual da %s. Se preferir falar com uma pessoa do time, é só pedir." % (voice["assistant_name"], business)
    return "Aqui é o atendimento virtual da %s, não uma pessoa. Se preferir falar com alguém do time, é só pedir." % business


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", _fold(text)) if len(token) > 1]


def _opening(text: str) -> str:
    return " ".join(_tokens(text)[:3])


def style_violations(
    draft: str,
    voice: Mapping[str, Any],
    *,
    template: str = "",
    question_field: Optional[str] = None,
    previous_seller: Sequence[str] = (),
) -> List[Dict[str, str]]:
    """Deterministic lint for text that reads as bot copy."""
    violations: List[Dict[str, str]] = []
    value = draft.casefold()
    for pattern in (*DEFAULT_FORBIDDEN_PHRASES, *(re.escape(item.casefold()) for item in voice.get("forbidden_phrases", []))):
        match = re.search(pattern, value)
        if match:
            violations.append({"kind": "style", "value": "phrase:%s" % match.group(0)})
    if "—" in draft or "–" in draft:
        violations.append({"kind": "style", "value": "dash"})
    if re.search(r"^\s*(?:[-*•]|\d+[.)])\s+\S", draft, re.M) and not re.search(r"^\s*(?:[-*•]|\d+[.)])\s+\S", template, re.M):
        violations.append({"kind": "style", "value": "list_formatting"})
    if "**" in draft or re.search(r"^\s*#+\s", draft, re.M):
        violations.append({"kind": "style", "value": "markdown"})
    emojis = len(_EMOJI.findall(draft))
    policy = voice.get("emoji", "light")
    if (policy == "none" and emojis) or (policy == "light" and emojis > 1):
        violations.append({"kind": "style", "value": "emoji"})
    if draft.count("!") > 2:
        violations.append({"kind": "style", "value": "exclamation"})
    limit = int(voice.get("max_chars", 320))
    if len(draft) > max(limit, int(len(template) * 1.3)):
        violations.append({"kind": "style", "value": "too_long"})
    if "?" in draft and not question_field and "?" not in template:
        violations.append({"kind": "style", "value": "unneeded_question"})
    opening = _opening(draft)
    if opening and any(opening == _opening(previous) for previous in previous_seller[-2:] if previous):
        violations.append({"kind": "style", "value": "repeated_opening"})
    return violations


def buyer_register(buyer_texts: Sequence[str]) -> Dict[str, Any]:
    """Describe how the buyer writes so the reply can mirror it."""
    texts = [text for text in buyer_texts if text and text.strip()][-6:]
    if not texts:
        return {"length": "curta", "informal": True, "emoji": False}
    words = sum(len(text.split()) for text in texts) / len(texts)
    joined = " ".join(texts)
    informal = bool(re.search(r"\b(?:vc|vcs|tb|tbm|pq|blz|kk+|rs+|td|q|pra|tá|ta|tô|to|beleza|valeu|oi|opa|e aí)\b", joined.casefold()))
    informal = informal or joined == joined.casefold()
    return {
        "length": "curta" if words <= 12 else "média" if words <= 40 else "longa",
        "informal": informal,
        "emoji": bool(_EMOJI.search(joined)),
    }


def select_examples(voice: Mapping[str, Any], query: str, k: int = 3) -> List[Dict[str, str]]:
    """Pick the owner examples most similar to the current turn (BM25)."""
    examples = [item for item in voice.get("examples", []) if item.get("seller")]
    if not examples:
        return []
    documents = [_tokens(" ".join(str(item.get(key, "")) for key in ("situation", "buyer"))) for item in examples]
    query_terms = set(_tokens(query))
    average = sum(len(doc) for doc in documents) / len(documents) or 1.0
    scores = []
    for index, doc in enumerate(documents):
        score = 0.0
        for term in query_terms:
            frequency = doc.count(term)
            if not frequency:
                continue
            containing = sum(1 for other in documents if term in other)
            idf = math.log(1 + (len(documents) - containing + 0.5) / (containing + 0.5))
            score += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * len(doc) / average))
        scores.append((score, -index))
    ranked = sorted(range(len(examples)), key=lambda index: scores[index], reverse=True)
    chosen = [index for index in ranked if scores[index][0] > 0][:k]
    if not chosen:
        chosen = list(range(min(k, len(examples))))
    return [{key: str(examples[index].get(key, "")) for key in ("situation", "buyer", "seller")} for index in chosen]


def validate_voice(voice: Any) -> None:
    """Raise ValueError when an owner voice block cannot be applied safely."""
    if voice is None:
        return
    if not isinstance(voice, Mapping):
        raise ValueError("voice deve ser um objeto")
    allowed = {"assistant_name", "disclose_ai", "tone", "address", "emoji", "max_chars", "forbidden_phrases", "examples"}
    unknown = sorted(set(voice) - allowed)
    if unknown:
        raise ValueError("voice tem chaves desconhecidas: %s" % ", ".join(unknown))
    for key in ("assistant_name", "tone"):
        if key in voice and (not isinstance(voice[key], str) or len(voice[key]) > 300):
            raise ValueError("voice.%s deve ser texto curto" % key)
    if "disclose_ai" in voice and not isinstance(voice["disclose_ai"], bool):
        raise ValueError("voice.disclose_ai deve ser booleano")
    if voice.get("address", "você") not in ADDRESS_FORMS:
        raise ValueError("voice.address deve ser 'você' ou 'tu'")
    if voice.get("emoji", "light") not in EMOJI_POLICIES:
        raise ValueError("voice.emoji deve ser none, light ou free")
    max_chars = voice.get("max_chars", 320)
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 80 <= max_chars <= 4000:
        raise ValueError("voice.max_chars deve ser inteiro entre 80 e 4000")
    phrases = voice.get("forbidden_phrases", [])
    if not isinstance(phrases, list) or not all(isinstance(item, str) and item.strip() for item in phrases):
        raise ValueError("voice.forbidden_phrases deve ser lista de textos")
    examples = voice.get("examples", [])
    if not isinstance(examples, list) or len(examples) > MAX_EXAMPLES:
        raise ValueError("voice.examples deve ser lista com até %d itens" % MAX_EXAMPLES)
    for index, example in enumerate(examples):
        if not isinstance(example, Mapping) or not isinstance(example.get("seller"), str) or not example["seller"].strip():
            raise ValueError("voice.examples[%d].seller é obrigatório" % index)
        for key in ("situation", "buyer", "seller"):
            if key in example and (not isinstance(example[key], str) or len(example[key]) > MAX_EXAMPLE_CHARS):
                raise ValueError("voice.examples[%d].%s deve ter até %d caracteres" % (index, key, MAX_EXAMPLE_CHARS))
