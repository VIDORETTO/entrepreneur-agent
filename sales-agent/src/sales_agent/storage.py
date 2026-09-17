"""SQLite persistence for private business state and durable effects."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .types import empty_conversation


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateStore:
    """Deep persistence seam used by configuration, runtime and adapters."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "state.sqlite3"
        self._lock = threading.RLock()
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS businesses (
                    business_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS business_versions (
                    business_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, version),
                    FOREIGN KEY (business_id) REFERENCES businesses(business_id)
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, conversation_id),
                    FOREIGN KEY (business_id) REFERENCES businesses(business_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, conversation_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS effects (
                    effect_key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    message_key TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    business_id TEXT NOT NULL,
                    offer_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    available INTEGER NOT NULL,
                    PRIMARY KEY (business_id, offer_id, variant)
                );
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    business_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    status TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, source_id, source_version)
                );
                CREATE TABLE IF NOT EXISTS discovery_sessions (
                    session_id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def loads(value: str) -> Any:
        return json.loads(value)

    def save_business(self, package: Dict[str, Any]) -> None:
        business_id = str(package["business"]["id"])
        with self._lock, self.connect() as db:
            row = db.execute("SELECT version FROM businesses WHERE business_id = ?", (business_id,)).fetchone()
            version = int(row["version"]) + 1 if row else 1
            db.execute(
                "INSERT INTO businesses VALUES (?, ?, ?, ?) ON CONFLICT(business_id) DO UPDATE SET version=excluded.version, payload=excluded.payload, updated_at=excluded.updated_at",
                (business_id, version, self.dumps(package), utc_now()),
            )
            db.execute(
                "INSERT OR REPLACE INTO business_versions VALUES (?, ?, ?, ?)",
                (business_id, version, self.dumps(package), utc_now()),
            )
            for offer in package.get("offers", []):
                stock = offer.get("stock", {})
                if offer.get("kind") == "physical" and isinstance(stock, dict):
                    for variant, amount in stock.items():
                        db.execute(
                            "INSERT INTO inventory(business_id, offer_id, variant, available) VALUES (?, ?, ?, ?) ON CONFLICT(business_id, offer_id, variant) DO NOTHING",
                            (business_id, offer["id"], str(variant), int(amount)),
                        )

    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM businesses WHERE business_id = ?", (business_id,)).fetchone()
        return self.loads(row["payload"]) if row else None

    def list_businesses(self) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM businesses ORDER BY business_id").fetchall()
        return [self.loads(row["payload"]) for row in rows]

    def list_business_versions(self, business_id: str) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT version, payload, created_at FROM business_versions WHERE business_id = ? ORDER BY version",
                (business_id,),
            ).fetchall()
        return [{"version": int(row["version"]), "created_at": row["created_at"], "package": self.loads(row["payload"])} for row in rows]

    def load_conversation(self, business_id: str, conversation_id: str, contact_id: str) -> Dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM conversations WHERE business_id = ? AND conversation_id = ?",
                (business_id, conversation_id),
            ).fetchone()
        if row:
            return self.loads(row["payload"])
        return empty_conversation(business_id, conversation_id, contact_id)

    def save_conversation(self, state: Dict[str, Any]) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?) ON CONFLICT(business_id, conversation_id) DO UPDATE SET version=excluded.version, payload=excluded.payload, updated_at=excluded.updated_at",
                (
                    state["business_id"],
                    state["conversation_id"],
                    int(state.get("version", 0)),
                    self.dumps(state),
                    utc_now(),
                ),
            )

    def get_event(self, business_id: str, conversation_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT result FROM events WHERE business_id = ? AND conversation_id = ? AND event_id = ?",
                (business_id, conversation_id, event_id),
            ).fetchone()
        return self.loads(row["result"]) if row else None

    def save_event(
        self, business_id: str, conversation_id: str, event_id: str, payload: Dict[str, Any], result: Dict[str, Any]
    ) -> bool:
        with self._lock, self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                    (business_id, conversation_id, event_id, self.dumps(payload), self.dumps(result), utc_now()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def reserve_effect(self, effect_key: str, kind: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        now = utc_now()
        with self._lock, self.connect() as db:
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
            if row:
                return False, {"status": row["status"], **self.loads(row["payload"])}
            db.execute(
                "INSERT INTO effects VALUES (?, ?, ?, ?, ?, ?)",
                (effect_key, kind, "reserved", self.dumps(payload), now, now),
            )
            return True, {"status": "reserved", **payload}

    def update_effect(self, effect_key: str, status: str, payload: Dict[str, Any]) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                "UPDATE effects SET status = ?, payload = ?, updated_at = ? WHERE effect_key = ?",
                (status, self.dumps(payload), utc_now(), effect_key),
            )

    def get_effect(self, effect_key: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
        if not row:
            return None
        return {"status": row["status"], **self.loads(row["payload"])}

    def enqueue_message(self, message_key: str, business_id: str, conversation_id: str, payload: Dict[str, Any]) -> bool:
        with self._lock, self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO outbox VALUES (?, ?, ?, ?, ?, ?)",
                    (message_key, business_id, conversation_id, self.dumps(payload), "pending", utc_now()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_outbox(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as db:
            if status:
                rows = db.execute("SELECT * FROM outbox WHERE status = ? ORDER BY created_at", (status,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM outbox ORDER BY created_at").fetchall()
        return [
            {
                "message_key": row["message_key"],
                "business_id": row["business_id"],
                "conversation_id": row["conversation_id"],
                "status": row["status"],
                **self.loads(row["payload"]),
            }
            for row in rows
        ]

    def cancel_followups(self, business_id: str, conversation_id: str) -> int:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'cancelled' WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'followup:%' AND status = 'pending'",
                (business_id, conversation_id),
            )
            return cursor.rowcount

    def cancel_followup(self, task_id: str) -> int:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'cancelled' WHERE message_key = ? AND status = 'pending'",
                ("followup:%s" % task_id,),
            )
            return cursor.rowcount

    def inventory(self, business_id: str, offer_id: str, variant: str) -> Optional[int]:
        with self.connect() as db:
            row = db.execute(
                "SELECT available FROM inventory WHERE business_id = ? AND offer_id = ? AND variant = ?",
                (business_id, offer_id, variant),
            ).fetchone()
        return int(row["available"]) if row else None

    def reserve_inventory(self, business_id: str, offer_id: str, variant: str, quantity: int) -> bool:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE inventory SET available = available - ? WHERE business_id = ? AND offer_id = ? AND variant = ? AND available >= ?",
                (quantity, business_id, offer_id, variant, quantity),
            )
            return cursor.rowcount == 1

    def put_source(self, source: Dict[str, Any]) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO knowledge_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(business_id, source_id, source_version) DO UPDATE SET title=excluded.title, content=excluded.content, locator=excluded.locator, status=excluded.status, origin=excluded.origin, content_hash=excluded.content_hash, backend=excluded.backend, updated_at=excluded.updated_at",
                (
                    source["business_id"],
                    source["source_id"],
                    source["source_version"],
                    source.get("title", source["source_id"]),
                    source["content"],
                    source.get("locator", source["source_id"]),
                    source.get("status", "approved"),
                    source.get("origin", "local"),
                    source["content_hash"],
                    source.get("backend", "sqlite-farol-v1"),
                    utc_now(),
                ),
            )

    def revoke_source(self, business_id: str, source_id: str, source_version: Optional[str] = None) -> int:
        with self._lock, self.connect() as db:
            if source_version:
                cursor = db.execute(
                    "UPDATE knowledge_sources SET status = 'revoked', updated_at = ? WHERE business_id = ? AND source_id = ? AND source_version = ?",
                    (utc_now(), business_id, source_id, source_version),
                )
            else:
                cursor = db.execute(
                    "UPDATE knowledge_sources SET status = 'revoked', updated_at = ? WHERE business_id = ? AND source_id = ?",
                    (utc_now(), business_id, source_id),
                )
            return cursor.rowcount

    def search_sources(self, business_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM knowledge_sources WHERE business_id = ? AND status = 'approved'",
                (business_id,),
            ).fetchall()
        query_tokens = {token.casefold() for token in query.split() if token.strip()}
        hits = []
        for row in rows:
            content = row["content"]
            haystack = (row["title"] + " " + content).casefold()
            overlap = sum(1 for token in query_tokens if token in haystack)
            phrase = 1 if query.casefold() in haystack else 0
            score = float(overlap) + phrase * 0.5
            if score <= 0:
                continue
            hits.append(
                {
                    "evidence_id": "%s:%s:%s" % (business_id, row["source_id"], row["source_version"]),
                    "business_id": business_id,
                    "source_id": row["source_id"],
                    "source_version": row["source_version"],
                    "content": content,
                    "locator": row["locator"],
                    "score": score,
                    "backend": row["backend"],
                    "origin": row["origin"],
                }
            )
        hits.sort(key=lambda item: (-item["score"], item["source_id"], item["source_version"]))
        return hits[:max_results]

    def save_discovery(self, session_id: str, business_id: str, payload: Dict[str, Any]) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO discovery_sessions VALUES (?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (session_id, business_id, self.dumps(payload), utc_now()),
            )

    def get_discovery(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM discovery_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return self.loads(row["payload"]) if row else None
