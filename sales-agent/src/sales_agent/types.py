"""Small domain records shared by the public seams.

The records are intentionally serialisable. Persisted state is the authority for
commercial facts; the model only supplies an interpretation proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Proposal:
    intent: str = "unknown"
    offer_id: Optional[str] = None
    facts: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    requested_action: Optional[str] = None
    model_name: str = "rules-v1"
    confidence: str = "deterministic"
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    evidence_id: str
    business_id: str
    source_id: str
    source_version: str
    content: str
    locator: str
    score: float
    backend: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "business_id": self.business_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "content": self.content,
            "locator": self.locator,
            "score": self.score,
            "backend": self.backend,
        }


@dataclass
class EngineResult:
    event_id: str
    conversation_id: str
    response: str
    action: Optional[Dict[str, Any]] = None
    state: Dict[str, Any] = field(default_factory=dict)
    duplicate: bool = False
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "conversation_id": self.conversation_id,
            "response": self.response,
            "action": self.action,
            "state": self.state,
            "duplicate": self.duplicate,
            "evidence": self.evidence,
            "trace": self.trace,
        }


def empty_conversation(business_id: str, conversation_id: str, contact_id: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "business_id": business_id,
        "conversation_id": conversation_id,
        "contact_id": contact_id,
        "channel": "cli",
        "version": 0,
        "responsible": "ai",
        "status": "active",
        "phase": "exploring",
        "intent": "unknown",
        "facts": {},
        "answered_fields": [],
        "pending": None,
        "quote": None,
        "operation": {"type": "none", "status": "none"},
        "follow_up_allowed": True,
        "history": [],
        "last_event_id": None,
        "last_interaction": None,
        "summary": "",
    }
