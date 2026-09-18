"""SQLite persistence for private business state and durable effects."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .types import empty_conversation

DATABASE_SCHEMA_VERSION = 2
OUTBOX_STATUSES = {"pending", "processing", "sent", "cancelled", "dead_letter"}
EFFECT_TRANSITIONS = {
    "reserved": {"unknown", "confirmed", "failed"},
    "unknown": {"confirmed", "failed"},
    "confirmed": set(),
    "failed": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def durable_key(namespace: str, *parts: str) -> str:
    """Build an unambiguous, log-safe idempotency key from scoped identifiers."""

    encoded = json.dumps(list(parts), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "%s:%s" % (namespace, hashlib.sha256(encoded).hexdigest())


class StateStore:
    """Deep persistence seam used by configuration, runtime and adapters."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._restrict_permissions(self.data_dir, 0o700)
        self.db_path = self.data_dir / "state.sqlite3"
        self._lock = threading.RLock()
        self._init_db()
        self._restrict_permissions(self.db_path, 0o600)

    @staticmethod
    def _restrict_permissions(path: Path, mode: int) -> None:
        """Keep local business state private on POSIX hosts.

        Windows does not implement POSIX mode bits consistently, so access
        control remains the responsibility of the containing user profile.
        """

        if os.name == "posix":
            path.chmod(mode)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _init_db(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
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
                    created_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT,
                    leased_until TEXT,
                    last_error TEXT,
                    updated_at TEXT
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
            self._migrate_schema(db)

    @staticmethod
    def _migrate_schema(db: sqlite3.Connection) -> None:
        """Apply additive migrations to databases created by older releases."""

        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        if version > DATABASE_SCHEMA_VERSION:
            raise RuntimeError(
                "banco usa schema %d, mas este runtime suporta até %d" % (version, DATABASE_SCHEMA_VERSION)
            )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(outbox)").fetchall()}
        migrations = {
            "attempts": "ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0",
            "available_at": "ALTER TABLE outbox ADD COLUMN available_at TEXT",
            "leased_until": "ALTER TABLE outbox ADD COLUMN leased_until TEXT",
            "last_error": "ALTER TABLE outbox ADD COLUMN last_error TEXT",
            "updated_at": "ALTER TABLE outbox ADD COLUMN updated_at TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                db.execute(statement)
        db.execute("UPDATE outbox SET available_at = COALESCE(available_at, created_at)")
        db.execute("UPDATE outbox SET updated_at = COALESCE(updated_at, created_at)")
        db.execute(
            "UPDATE outbox SET status = 'pending', last_error = 'processing lease missing during migration' "
            "WHERE status = 'processing' AND leased_until IS NULL"
        )
        db.execute("CREATE INDEX IF NOT EXISTS outbox_delivery_idx ON outbox(status, available_at, leased_until)")
        db.execute("PRAGMA user_version = %d" % DATABASE_SCHEMA_VERSION)

    def schema_version(self) -> int:
        with self.connect() as db:
            return int(db.execute("PRAGMA user_version").fetchone()[0])

    def integrity_report(self) -> Dict[str, Any]:
        with self.connect() as db:
            integrity_rows = [row[0] for row in db.execute("PRAGMA integrity_check").fetchall()]
            foreign_key_rows = [tuple(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
            outbox = {
                row["status"]: int(row["amount"])
                for row in db.execute("SELECT status, COUNT(*) AS amount FROM outbox GROUP BY status").fetchall()
            }
            effects = {
                row["status"]: int(row["amount"])
                for row in db.execute("SELECT status, COUNT(*) AS amount FROM effects GROUP BY status").fetchall()
            }
        return {
            "ok": integrity_rows == ["ok"] and not foreign_key_rows,
            "schema_version": self.schema_version(),
            "supported_schema_version": DATABASE_SCHEMA_VERSION,
            "integrity": integrity_rows,
            "foreign_key_violations": foreign_key_rows,
            "outbox": outbox,
            "effects": effects,
        }

    def backup_to(self, destination: Path | str) -> Path:
        output = Path(destination).expanduser().resolve()
        if output == self.db_path:
            raise ValueError("backup não pode sobrescrever o banco ativo")
        if output.exists():
            raise FileExistsError("destino de backup já existe: %s" % output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(str(output)) as target:
            source.backup(target)
        self._restrict_permissions(output, 0o600)
        return output

    @staticmethod
    def _validate_restore_source(source: Path) -> None:
        if not source.is_file() or source.is_symlink():
            raise ValueError("backup precisa ser um arquivo SQLite regular")
        try:
            with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as db:
                integrity = [row[0] for row in db.execute("PRAGMA integrity_check").fetchall()]
                version = int(db.execute("PRAGMA user_version").fetchone()[0])
                tables = {
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
                }
        except sqlite3.DatabaseError as exc:
            raise ValueError("backup SQLite inválido: %s" % exc) from exc
        required = {"businesses", "conversations", "events", "effects", "outbox"}
        if integrity != ["ok"] or not required.issubset(tables):
            raise ValueError("backup falhou na verificação de integridade ou estrutura")
        if version > DATABASE_SCHEMA_VERSION:
            raise ValueError("backup usa schema mais novo que este runtime")

    def restore_from(self, source: Path | str, backup_current: Path | str) -> Dict[str, Any]:
        input_path = Path(source).expanduser().resolve()
        current_backup = Path(backup_current).expanduser().resolve()
        if input_path in {self.db_path, current_backup} or current_backup == self.db_path:
            raise ValueError("origem, banco ativo e backup de segurança precisam ser arquivos distintos")
        self._validate_restore_source(input_path)
        saved = self.backup_to(current_backup)
        with self._lock, sqlite3.connect(str(input_path)) as source_db, self.connect() as target_db:
            source_db.backup(target_db)
        self._init_db()
        report = self.integrity_report()
        if not report["ok"]:
            raise RuntimeError("restauração terminou com falha de integridade; backup atual preservado em %s" % saved)
        return {"restored_from": str(input_path), "previous_backup": str(saved), "integrity": report}

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def loads(value: str) -> Any:
        return json.loads(value)

    def save_business(self, package: Dict[str, Any]) -> None:
        business_id = str(package["business"]["id"])
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
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

    def save_conversation_if_version(self, state: Dict[str, Any], expected_version: int) -> bool:
        """Persist a conversation only if no other worker advanced it."""

        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT version FROM conversations WHERE business_id = ? AND conversation_id = ?",
                (state["business_id"], state["conversation_id"]),
            ).fetchone()
            current_version = int(row["version"]) if row else 0
            if current_version != expected_version:
                return False
            if row:
                cursor = db.execute(
                    "UPDATE conversations SET version = ?, payload = ?, updated_at = ? "
                    "WHERE business_id = ? AND conversation_id = ? AND version = ?",
                    (
                        int(state.get("version", 0)),
                        self.dumps(state),
                        utc_now(),
                        state["business_id"],
                        state["conversation_id"],
                        expected_version,
                    ),
                )
                return cursor.rowcount == 1
            try:
                db.execute(
                    "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                    (
                        state["business_id"],
                        state["conversation_id"],
                        int(state.get("version", 0)),
                        self.dumps(state),
                        utc_now(),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

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

    def commit_event(
        self,
        state: Dict[str, Any],
        expected_version: int,
        event: Dict[str, Any],
        result: Dict[str, Any],
        message_key: str,
        outbox_payload: Dict[str, Any],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Atomically persist conversation state, audit event and outbox intent."""

        business_id = str(event["business_id"])
        conversation_id = str(event["conversation_id"])
        event_id = str(event["event_id"])
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT result FROM events WHERE business_id = ? AND conversation_id = ? AND event_id = ?",
                (business_id, conversation_id, event_id),
            ).fetchone()
            if existing:
                return "duplicate", self.loads(existing["result"])
            row = db.execute(
                "SELECT version FROM conversations WHERE business_id = ? AND conversation_id = ?",
                (business_id, conversation_id),
            ).fetchone()
            current_version = int(row["version"]) if row else 0
            if current_version != expected_version:
                return "stale", None
            if row:
                db.execute(
                    "UPDATE conversations SET version = ?, payload = ?, updated_at = ? "
                    "WHERE business_id = ? AND conversation_id = ? AND version = ?",
                    (
                        int(state["version"]),
                        self.dumps(state),
                        now,
                        business_id,
                        conversation_id,
                        expected_version,
                    ),
                )
            else:
                db.execute(
                    "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                    (business_id, conversation_id, int(state["version"]), self.dumps(state), now),
                )
            db.execute(
                "INSERT OR IGNORE INTO outbox(message_key, business_id, conversation_id, payload, status, created_at, "
                "attempts, available_at, leased_until, last_error, updated_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, NULL, NULL, ?)",
                (message_key, business_id, conversation_id, self.dumps(outbox_payload), now, now, now),
            )
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                (business_id, conversation_id, event_id, self.dumps(event), self.dumps(result), now),
            )
            return "committed", None

    def commit_stale_event(
        self,
        event: Dict[str, Any],
        result: Dict[str, Any],
        *,
        reconciled_state: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Atomically audit a suppressed response and optional reconciliation state."""

        business_id = str(event["business_id"])
        conversation_id = str(event["conversation_id"])
        event_id = str(event["event_id"])
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT result FROM events WHERE business_id = ? AND conversation_id = ? AND event_id = ?",
                (business_id, conversation_id, event_id),
            ).fetchone()
            if existing:
                return "duplicate", self.loads(existing["result"])
            if reconciled_state is not None:
                row = db.execute(
                    "SELECT version FROM conversations WHERE business_id = ? AND conversation_id = ?",
                    (business_id, conversation_id),
                ).fetchone()
                current_version = int(row["version"]) if row else 0
                if expected_version is None or current_version != expected_version:
                    return "stale", None
                db.execute(
                    "UPDATE conversations SET version = ?, payload = ?, updated_at = ? "
                    "WHERE business_id = ? AND conversation_id = ? AND version = ?",
                    (
                        int(reconciled_state["version"]),
                        self.dumps(reconciled_state),
                        now,
                        business_id,
                        conversation_id,
                        expected_version,
                    ),
                )
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                (business_id, conversation_id, event_id, self.dumps(event), self.dumps(result), now),
            )
            return "committed", None

    def reserve_effect(self, effect_key: str, kind: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        now = utc_now()
        with self._lock, self.connect() as db:
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
            if row:
                return False, {**self.loads(row["payload"]), "status": row["status"]}
            db.execute(
                "INSERT INTO effects VALUES (?, ?, ?, ?, ?, ?)",
                (effect_key, kind, "reserved", self.dumps(payload), now, now),
            )
            return True, {**payload, "status": "reserved"}

    def reserve_checkout_effect(
        self,
        effect_key: str,
        payload: Dict[str, Any],
        *,
        business_id: str,
        offer_id: str,
        variant: str,
        quantity: int,
    ) -> Tuple[str, Dict[str, Any]]:
        """Reserve the idempotent checkout effect and inventory atomically."""

        if quantity <= 0:
            raise ValueError("quantity deve ser positiva")
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)
            ).fetchone()
            if existing:
                return "existing", {**self.loads(existing["payload"]), "status": existing["status"]}
            inventory = db.execute(
                "SELECT available FROM inventory WHERE business_id = ? AND offer_id = ? AND variant = ?",
                (business_id, offer_id, variant),
            ).fetchone()
            if not inventory or int(inventory["available"]) < quantity:
                failed = {**payload, "reason": "out_of_stock"}
                db.execute(
                    "INSERT INTO effects VALUES (?, 'checkout', 'failed', ?, ?, ?)",
                    (effect_key, self.dumps(failed), now, now),
                )
                return "out_of_stock", {**failed, "status": "failed"}
            db.execute(
                "UPDATE inventory SET available = available - ? "
                "WHERE business_id = ? AND offer_id = ? AND variant = ?",
                (quantity, business_id, offer_id, variant),
            )
            reservation = {
                **payload,
                "inventory_reservation": {
                    "business_id": business_id,
                    "offer_id": offer_id,
                    "variant": variant,
                    "quantity": quantity,
                    "released": False,
                },
            }
            db.execute(
                "INSERT INTO effects VALUES (?, 'checkout', 'reserved', ?, ?, ?)",
                (effect_key, self.dumps(reservation), now, now),
            )
            return "reserved", {**reservation, "status": "reserved"}

    def update_effect(self, effect_key: str, status: str, payload: Dict[str, Any]) -> None:
        with self._lock, self.connect() as db:
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
            if not row:
                raise ValueError("efeito não encontrado: %s" % effect_key)
            if status not in EFFECT_TRANSITIONS.get(row["status"], set()):
                raise ValueError("transição de efeito inválida: %s -> %s" % (row["status"], status))
            merged = {**self.loads(row["payload"]), **payload}
            db.execute(
                "UPDATE effects SET status = ?, payload = ?, updated_at = ? WHERE effect_key = ?",
                (status, self.dumps(merged), utc_now(), effect_key),
            )

    def get_effect(self, effect_key: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
        if not row:
            return None
        return {**self.loads(row["payload"]), "status": row["status"]}

    def list_effects(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as db:
            if status:
                rows = db.execute(
                    "SELECT effect_key, kind, status, payload, created_at, updated_at FROM effects "
                    "WHERE status = ? ORDER BY created_at, effect_key",
                    (status,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT effect_key, kind, status, payload, created_at, updated_at FROM effects "
                    "ORDER BY created_at, effect_key"
                ).fetchall()
        return [
            {
                **self.loads(row["payload"]),
                "effect_key": row["effect_key"],
                "kind": row["kind"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def reconcile_effect(self, effect_key: str, resolution: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve an unknown/reserved effect and compensate inventory on failure."""

        if resolution not in {"confirmed", "failed"}:
            raise ValueError("resolution deve ser confirmed ou failed")
        if details is not None and not isinstance(details, dict):
            raise ValueError("details precisa ser um objeto")
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT kind, status, payload FROM effects WHERE effect_key = ?", (effect_key,)
            ).fetchone()
            if not row:
                raise ValueError("efeito não encontrado: %s" % effect_key)
            stored_payload = self.loads(row["payload"])
            protected = {"business_id", "conversation_id", "quote_id", "inventory_reservation", "effect_key"}
            for field in protected.intersection(details or {}):
                if details[field] != stored_payload.get(field):
                    raise ValueError("details não pode alterar metadado protegido: %s" % field)
            payload = {**stored_payload, **(details or {})}
            business_id = payload.get("business_id")
            conversation_id = payload.get("conversation_id")
            conversation_row = None
            awaiting_reconciliation = False
            if business_id and conversation_id:
                conversation_row = db.execute(
                    "SELECT version, payload FROM conversations WHERE business_id = ? AND conversation_id = ?",
                    (str(business_id), str(conversation_id)),
                ).fetchone()
                if conversation_row:
                    conversation_state = self.loads(conversation_row["payload"])
                    operation = conversation_state.get("operation") or {}
                    awaiting_reconciliation = operation.get("status") == "unknown" and (
                        operation.get("effect_key") == effect_key
                        or operation.get("quote_id") == payload.get("quote_id")
                    )
            if row["status"] not in {"reserved", "unknown"}:
                acknowledges_terminal = awaiting_reconciliation and row["status"] == resolution
                cancels_prepared_checkout = (
                    awaiting_reconciliation
                    and row["status"] == "confirmed"
                    and resolution == "failed"
                    and row["kind"] == "checkout"
                    and stored_payload.get("charged") is False
                    and payload.get("cancelled") is True
                    and isinstance(payload.get("resolution_source"), str)
                    and bool(payload["resolution_source"].strip())
                )
                if not acknowledges_terminal and not cancels_prepared_checkout:
                    raise ValueError("efeito não está pendente de conciliação: %s" % row["status"])
            if row["kind"] == "checkout" and resolution == "confirmed":
                if not payload.get("checkout_id") or not payload.get("url") or payload.get("charged") is not False:
                    raise ValueError("checkout confirmado exige checkout_id, url e charged=false")
            reservation = payload.get("inventory_reservation")
            if resolution == "failed" and isinstance(reservation, dict) and not reservation.get("released"):
                db.execute(
                    "UPDATE inventory SET available = available + ? "
                    "WHERE business_id = ? AND offer_id = ? AND variant = ?",
                    (
                        int(reservation["quantity"]),
                        str(reservation["business_id"]),
                        str(reservation["offer_id"]),
                        str(reservation["variant"]),
                    ),
                )
                reservation = {**reservation, "released": True, "released_at": now}
                payload["inventory_reservation"] = reservation
            payload["reconciled_at"] = now
            db.execute(
                "UPDATE effects SET status = ?, payload = ?, updated_at = ? WHERE effect_key = ?",
                (resolution, self.dumps(payload), now, effect_key),
            )
            if business_id and conversation_id:
                if conversation_row:
                    state = self.loads(conversation_row["payload"])
                    operation = state.get("operation") or {}
                    if operation.get("effect_key") == effect_key or operation.get("quote_id") == payload.get("quote_id"):
                        if resolution == "confirmed":
                            state["operation"] = {
                                "type": row["kind"],
                                "effect_key": effect_key,
                                **payload,
                                "status": "confirmed",
                            }
                            state["phase"] = "action_in_progress"
                        else:
                            state["operation"] = {
                                "type": row["kind"],
                                "status": "failed",
                                "effect_key": effect_key,
                                "reason": payload.get("reason", "reconciled_as_failed"),
                            }
                            state["quote"] = None
                            state.setdefault("facts", {})["_checkout_attempt"] = int(
                                state.get("facts", {}).get("_checkout_attempt", 0)
                            ) + 1
                            state["phase"] = "ready_to_advance"
                        state["pending"] = None
                        state["version"] = int(conversation_row["version"]) + 1
                        state.setdefault("history", []).append(
                            {
                                "event_id": "reconcile:%s" % effect_key,
                                "text": "",
                                "response": "",
                                "action": {"type": "effect_reconciliation", "status": resolution, "effect_key": effect_key},
                            }
                        )
                        state["history"] = state["history"][-40:]
                        db.execute(
                            "UPDATE conversations SET version = ?, payload = ?, updated_at = ? "
                            "WHERE business_id = ? AND conversation_id = ?",
                            (
                                state["version"],
                                self.dumps(state),
                                now,
                                str(business_id),
                                str(conversation_id),
                            ),
                        )
            return {**payload, "effect_key": effect_key, "kind": row["kind"], "status": resolution}

    def enqueue_message(self, message_key: str, business_id: str, conversation_id: str, payload: Dict[str, Any]) -> bool:
        now = utc_now()
        with self._lock, self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO outbox(message_key, business_id, conversation_id, payload, status, created_at, "
                    "attempts, available_at, leased_until, last_error, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, ?)",
                    (message_key, business_id, conversation_id, self.dumps(payload), "pending", now, now, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_outbox(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status is not None and status not in OUTBOX_STATUSES:
            raise ValueError("status de outbox inválido: %s" % status)
        with self.connect() as db:
            if status:
                rows = db.execute("SELECT * FROM outbox WHERE status = ? ORDER BY created_at", (status,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM outbox ORDER BY created_at").fetchall()
        return [self._outbox_row(row) for row in rows]

    def claim_outbox(self, limit: int = 10, lease_seconds: int = 60) -> List[Dict[str, Any]]:
        """Lease eligible messages to one delivery worker."""

        if limit < 1 or limit > 100:
            raise ValueError("limit deve estar entre 1 e 100")
        if lease_seconds < 1 or lease_seconds > 3600:
            raise ValueError("lease_seconds deve estar entre 1 e 3600")
        now = datetime.now(timezone.utc)
        now_text = now.isoformat(timespec="seconds")
        leased_until = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT message_key FROM outbox "
                "WHERE status = 'pending' AND COALESCE(available_at, created_at) <= ? "
                "ORDER BY created_at, message_key LIMIT ?",
                (now_text, limit),
            ).fetchall()
            keys = [row["message_key"] for row in rows]
            for key in keys:
                db.execute(
                    "UPDATE outbox SET status = 'processing', attempts = attempts + 1, leased_until = ?, updated_at = ? "
                    "WHERE message_key = ? AND status = 'pending'",
                    (leased_until, now_text, key),
                )
            if not keys:
                return []
            placeholders = ",".join("?" for _ in keys)
            claimed = db.execute(
                "SELECT * FROM outbox WHERE message_key IN (%s) ORDER BY created_at, message_key" % placeholders,
                keys,
            ).fetchall()
        return [self._outbox_row(row) for row in claimed]

    @classmethod
    def _outbox_row(cls, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            **cls.loads(row["payload"]),
            "message_key": row["message_key"],
            "business_id": row["business_id"],
            "conversation_id": row["conversation_id"],
            "status": row["status"],
            "attempts": int(row["attempts"]),
            "available_at": row["available_at"],
            "leased_until": row["leased_until"],
            "last_error": row["last_error"],
        }

    def ack_outbox(self, message_key: str) -> bool:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'sent', leased_until = NULL, last_error = NULL, updated_at = ? "
                "WHERE message_key = ? AND status = 'processing'",
                (utc_now(), message_key),
            )
            return cursor.rowcount == 1

    def nack_outbox(self, message_key: str, error: str, *, max_attempts: int = 5, delay_seconds: int = 30) -> str:
        if not error.strip():
            raise ValueError("error não pode ser vazio")
        if max_attempts < 1 or delay_seconds < 0:
            raise ValueError("parâmetros de retry inválidos")
        now = datetime.now(timezone.utc)
        with self._lock, self.connect() as db:
            row = db.execute(
                "SELECT attempts, status FROM outbox WHERE message_key = ?", (message_key,)
            ).fetchone()
            if not row or row["status"] != "processing":
                raise ValueError("mensagem não está em processamento: %s" % message_key)
            status = "dead_letter" if int(row["attempts"]) >= max_attempts else "pending"
            available_at = (now + timedelta(seconds=delay_seconds)).isoformat(timespec="seconds")
            db.execute(
                "UPDATE outbox SET status = ?, available_at = ?, leased_until = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ?",
                (status, available_at, error[:2000], now.isoformat(timespec="seconds"), message_key),
            )
            return status

    def recover_expired_outbox(self) -> int:
        now = utc_now()
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'pending', leased_until = NULL, last_error = 'delivery lease expired', "
                "available_at = ?, updated_at = ? WHERE status = 'processing' AND leased_until <= ?",
                (now, now, now),
            )
            return cursor.rowcount

    def cancel_followups(self, business_id: str, conversation_id: str) -> int:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'followup:%' "
                "AND status IN ('pending', 'processing')",
                (utc_now(), business_id, conversation_id),
            )
            return cursor.rowcount

    def cancel_followup(self, business_id: str, conversation_id: str, task_id: str) -> int:
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, updated_at = ? "
                "WHERE message_key = ? AND business_id = ? AND conversation_id = ? "
                "AND status IN ('pending', 'processing')",
                (utc_now(), durable_key("followup", business_id, conversation_id, task_id), business_id, conversation_id),
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
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity deve ser um inteiro positivo")
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
