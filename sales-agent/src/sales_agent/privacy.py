"""Local data subject operations and report redaction."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .storage import StateStore

PERSONAL_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)"),
    re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)"),
    re.compile(r"(?<![A-Za-z0-9])(?:\+55\s*)?(?:\(?\d{2}\)?[\s-]*)?9?\d{4}[\s-]*\d{4}(?![A-Za-z0-9])"),
)


def redact_data(value: Any) -> Any:
    """Remove common Brazilian contact identifiers from report structures."""

    if isinstance(value, str):
        for pattern in PERSONAL_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items()}
    return value


class PrivacyManager:
    def __init__(self, store: StateStore):
        self.store = store

    def export(self, business_id: str, contact: str) -> Dict[str, Any]:
        if not business_id or not contact:
            raise ValueError("negócio e contato são obrigatórios")
        with self.store.connect() as db:
            rows = db.execute("SELECT conversation_id, payload FROM conversations WHERE business_id = ?", (business_id,))
            conversations = [self.store.loads(row["payload"]) for row in rows
                             if self.store.loads(row["payload"]).get("contact_id") == contact]
            events = []
            messages = []
            effects = []
            for conversation in conversations:
                for row in db.execute("SELECT payload, result FROM events WHERE business_id = ? AND conversation_id = ? ORDER BY created_at", (business_id, conversation["conversation_id"])):
                    events.append({"event": self.store.loads(row["payload"]), "result": self.store.loads(row["result"])})
                for row in db.execute("SELECT payload FROM effects"):
                    payload = self.store.loads(row["payload"])
                    if payload.get("business_id") == business_id and payload.get("conversation_id") == conversation["conversation_id"]:
                        effects.append(payload)
            for row in db.execute("SELECT text, event_payload, received_at FROM inbound_messages WHERE business_id = ? AND contact_id = ? ORDER BY received_at", (business_id, contact)):
                messages.append({"text": row["text"], "event": self.store.loads(row["event_payload"]), "received_at": row["received_at"]})
        return {"business_id": business_id, "contact": contact, "conversations": conversations,
                "events": events, "messages": messages, "effects": effects}

    def _pseudonym(self, business_id: str, contact: str) -> str:
        path = self.store.data_dir / "privacy.key"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(os.urandom(32))
        key = path.read_bytes()
        return "pseudonym:" + hmac.new(key, (business_id + "\0" + contact).encode(), hashlib.sha256).hexdigest()

    def erase(self, business_id: str, contact: str) -> Dict[str, Any]:
        if not business_id or not contact:
            raise ValueError("negócio e contato são obrigatórios")
        pseudonym = self._pseudonym(business_id, contact)
        with self.store._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT conversation_id, payload FROM conversations WHERE business_id = ?", (business_id,)).fetchall()
            ids = [str(row["conversation_id"]) for row in rows
                   if self.store.loads(row["payload"]).get("contact_id") == contact]
            db.execute("DELETE FROM inbound_messages WHERE business_id = ? AND contact_id = ?", (business_id, contact))
            for conversation_id in ids:
                for row in db.execute("SELECT effect_key, payload FROM effects").fetchall():
                    payload = self.store.loads(row["payload"])
                    if payload.get("business_id") == business_id and payload.get("conversation_id") == conversation_id:
                        payload["conversation_id"] = pseudonym
                        payload["pseudonym"] = pseudonym
                        payload.pop("contact_id", None)
                        db.execute("UPDATE effects SET payload = ? WHERE effect_key = ?", (self.store.dumps(redact_data(payload)), row["effect_key"]))
                db.execute("DELETE FROM events WHERE business_id = ? AND conversation_id = ?", (business_id, conversation_id))
                db.execute("DELETE FROM conversations WHERE business_id = ? AND conversation_id = ?", (business_id, conversation_id))
                db.execute("DELETE FROM inbound_messages WHERE business_id = ? AND conversation_id = ?", (business_id, conversation_id))
                db.execute("DELETE FROM outbox WHERE business_id = ? AND conversation_id = ? AND status IN ('pending', 'cancelled')", (business_id, conversation_id))
                db.execute("UPDATE outbox SET conversation_id = ?, payload = '{}' WHERE business_id = ? AND conversation_id = ?", (pseudonym, business_id, conversation_id))
                db.execute("UPDATE outbound_ledger SET conversation_id = ? WHERE business_id = ? AND conversation_id = ?", (pseudonym, business_id, conversation_id))
                db.execute("UPDATE channel_events SET conversation_id = ?, payload = '{}' WHERE business_id = ? AND conversation_id = ?", (pseudonym, business_id, conversation_id))
                db.execute("UPDATE supervisor_reviews SET conversation_id = ?, payload = '{}' WHERE business_id = ? AND conversation_id = ?", (pseudonym, business_id, conversation_id))
            db.execute("CREATE TABLE IF NOT EXISTS privacy_audit (id TEXT PRIMARY KEY, business_id TEXT NOT NULL, pseudonym TEXT NOT NULL, operation TEXT NOT NULL, count INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execute("INSERT INTO privacy_audit VALUES (?, ?, ?, 'erase', ?, ?)",
                       (os.urandom(16).hex(), business_id, pseudonym, len(ids), datetime.now(timezone.utc).isoformat()))
        return {"business_id": business_id, "pseudonym": pseudonym, "erased_conversations": len(ids)}

    def purge(self, business_id: str, *, retention_days: Optional[int] = None, before: Optional[str] = None) -> Dict[str, Any]:
        if not business_id:
            raise ValueError("negócio obrigatório")
        if retention_days is None:
            package = self.store.get_business(business_id)
            if package is None:
                raise ValueError("negócio não encontrado")
            retention_days = package.get("privacy", {}).get("retention_days", 180)
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or retention_days < 0:
            raise ValueError("retention_days inválido")
        if retention_days == 0 and before is None:
            return {"business_id": business_id, "removed_events": 0, "removed_conversations": 0, "disabled": True}
        cutoff = datetime.fromisoformat(before.replace("Z", "+00:00")) if before else datetime.now(timezone.utc) - timedelta(days=retention_days)
        if cutoff.tzinfo is None:
            raise ValueError("before exige fuso")
        cutoff_text = cutoff.astimezone(timezone.utc).isoformat()
        with self.store._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            events = db.execute("DELETE FROM events WHERE business_id = ? AND created_at < ?", (business_id, cutoff_text)).rowcount
            db.execute("DELETE FROM inbound_messages WHERE business_id = ? AND received_at < ?", (business_id, cutoff_text))
            old_rows = db.execute("SELECT conversation_id, payload FROM conversations WHERE business_id = ? AND updated_at < ?", (business_id, cutoff_text)).fetchall()
            removed = 0
            for row in old_rows:
                conversation_id = row["conversation_id"]
                pending = db.execute("SELECT 1 FROM outbox WHERE business_id = ? AND conversation_id = ? AND status IN ('pending', 'processing', 'unknown') LIMIT 1", (business_id, conversation_id)).fetchone()
                if pending:
                    state = self.store.loads(row["payload"])
                    state["history"] = []
                    state["last_interaction"] = None
                    db.execute("UPDATE conversations SET payload = ? WHERE business_id = ? AND conversation_id = ?", (self.store.dumps(state), business_id, conversation_id))
                else:
                    db.execute("DELETE FROM conversations WHERE business_id = ? AND conversation_id = ?", (business_id, conversation_id))
                    removed += 1
            db.execute("CREATE TABLE IF NOT EXISTS privacy_audit (id TEXT PRIMARY KEY, business_id TEXT NOT NULL, pseudonym TEXT NOT NULL, operation TEXT NOT NULL, count INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execute("INSERT INTO privacy_audit VALUES (?, ?, '', 'purge', ?, ?)",
                       (os.urandom(16).hex(), business_id, events, datetime.now(timezone.utc).isoformat()))
        return {"business_id": business_id, "removed_events": events, "removed_conversations": removed, "before": cutoff_text}
