"""SQLite persistence for private business state and durable effects."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .clock import Clock, SystemClock
from .types import empty_conversation

DATABASE_SCHEMA_VERSION = 13
OUTBOX_STATUSES = {"pending", "processing", "sent", "cancelled", "dead_letter", "unknown", "observed", "window_closed"}
EFFECT_TRANSITIONS = {
    "reserved": {"unknown", "confirmed", "failed"},
    "unknown": {"confirmed", "failed"},
    "confirmed": set(),
    "failed": set(),
}


def utc_now() -> str:
    return SystemClock().now()


def reservation_expired(payload: Mapping[str, Any], now: datetime) -> bool:
    """Return whether a pending effect reservation can no longer be trusted."""

    expires_at = payload.get("reservation_expires_at")
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= now
    except (TypeError, ValueError):
        # A malformed lease must fail closed. Treating it as live would leave
        # an effect permanently stuck in ``reserved``.
        return True


def normalize_iso_datetime(value: str) -> str:
    """Canonicalize an ISO-8601 value to a UTC offset-aware timestamp."""

    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def durable_key(namespace: str, *parts: str) -> str:
    """Build an unambiguous, log-safe idempotency key from scoped identifiers."""

    encoded = json.dumps(list(parts), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "%s:%s" % (namespace, hashlib.sha256(encoded).hexdigest())


def _plain_text(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(character)
    )


def _requested_topics(query: str) -> List[set[str]]:
    value = _plain_text(query)
    topics = []
    definitions = (
        {"garantia"},
        {"troca"},
        {"devolucao", "devolucoes", "reembolso"},
        {"preco", "custa", "valor", "custo"},
        {"acesso", "duracao", "liberacao", "meses"},
        {"entrega", "prazo", "chegar", "envio"},
        {"pagamento", "pix", "cartao", "parcelamento"},
        {"estoque", "disponivel", "disponibilidade", "tamanho"},
    )
    for terms in definitions:
        if any(term in value for term in terms):
            topics.append(terms)
    return topics


class StateStore:
    """Deep persistence seam used by configuration, runtime and adapters."""

    def __init__(self, data_dir: Union[Path, str], clock: Optional[Clock] = None):
        self.clock = clock or SystemClock()
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
                    lease_owner TEXT,
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
                    scope TEXT NOT NULL DEFAULT '',
                    audience TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    valid_from TEXT,
                    valid_until TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    generation TEXT,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, source_id, source_version)
                );
                CREATE TABLE IF NOT EXISTS knowledge_revocations (
                    business_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_version TEXT,
                    reason TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (business_id, source_id, source_version)
                );
                CREATE TABLE IF NOT EXISTS knowledge_governance_events (
                    event_id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_version TEXT,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS discovery_sessions (
                    session_id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inbound_messages (
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    contact_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    text TEXT NOT NULL,
                    event_payload TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    turn_id TEXT,
                    PRIMARY KEY (business_id, conversation_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS channel_events (
                    channel TEXT NOT NULL,
                    external_event_id TEXT NOT NULL,
                    business_id TEXT,
                    conversation_id TEXT,
                    status TEXT NOT NULL,
                    reason TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (channel, external_event_id)
                );
                CREATE TABLE IF NOT EXISTS outbound_ledger (
                    message_key TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    provider_message_id TEXT,
                    content_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    sent_at TEXT
                );
                CREATE INDEX IF NOT EXISTS outbound_ledger_provider_idx
                    ON outbound_ledger(business_id, conversation_id, provider_message_id);
                CREATE INDEX IF NOT EXISTS outbound_ledger_content_idx
                    ON outbound_ledger(business_id, conversation_id, content_sha256, state);
                CREATE TABLE IF NOT EXISTS operating_modes (
                    scope_key TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    cohort TEXT NOT NULL,
                    limits TEXT NOT NULL,
                    evaluated_package_version TEXT,
                    evaluated_package_fingerprint TEXT,
                    evaluated_model TEXT,
                    evaluated_backend TEXT,
                    reason TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pilot_metrics (
                    scope_key TEXT PRIMARY KEY,
                    counters TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pilot_reservations (
                    scope_key TEXT NOT NULL,
                    reservation_key TEXT NOT NULL,
                    estimated_cost REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scope_key, reservation_key)
                );
                CREATE TABLE IF NOT EXISTS supervisor_reviews (
                    review_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    business_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    package_version TEXT,
                    state_version INTEGER,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS supervisor_settings (
                    scope_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    policy TEXT NOT NULL DEFAULT 'optional',
                    correction_limit INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS privacy_audit (
                    id TEXT PRIMARY KEY, business_id TEXT NOT NULL, pseudonym TEXT NOT NULL,
                    operation TEXT NOT NULL, count INTEGER NOT NULL, created_at TEXT NOT NULL
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
            "lease_owner": "ALTER TABLE outbox ADD COLUMN lease_owner TEXT",
            "last_error": "ALTER TABLE outbox ADD COLUMN last_error TEXT",
            "updated_at": "ALTER TABLE outbox ADD COLUMN updated_at TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                db.execute(statement)
        db.execute("UPDATE outbox SET available_at = COALESCE(available_at, created_at)")
        db.execute("UPDATE outbox SET updated_at = COALESCE(updated_at, created_at)")
        db.execute(
            "UPDATE outbox SET status = 'unknown', last_error = 'processing lease missing; delivery outcome is unknown' "
            "WHERE status = 'processing' AND leased_until IS NULL"
        )
        db.execute("CREATE INDEX IF NOT EXISTS outbox_delivery_idx ON outbox(status, available_at, leased_until)")
        source_columns = {row["name"] for row in db.execute("PRAGMA table_info(knowledge_sources)").fetchall()}
        source_migrations = {
            "scope": "ALTER TABLE knowledge_sources ADD COLUMN scope TEXT NOT NULL DEFAULT ''",
            "audience": "ALTER TABLE knowledge_sources ADD COLUMN audience TEXT NOT NULL DEFAULT ''",
            "subject": "ALTER TABLE knowledge_sources ADD COLUMN subject TEXT NOT NULL DEFAULT ''",
            "valid_from": "ALTER TABLE knowledge_sources ADD COLUMN valid_from TEXT",
            "valid_until": "ALTER TABLE knowledge_sources ADD COLUMN valid_until TEXT",
            "active": "ALTER TABLE knowledge_sources ADD COLUMN active INTEGER NOT NULL DEFAULT 1",
            "generation": "ALTER TABLE knowledge_sources ADD COLUMN generation TEXT",
            "review_status": "ALTER TABLE knowledge_sources ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending_review'",
        }
        had_review_status = "review_status" in source_columns
        for column, statement in source_migrations.items():
            if column not in source_columns:
                db.execute(statement)
        if not had_review_status:
            db.execute("UPDATE knowledge_sources SET review_status = 'pending_review'")
        db.execute(
            "INSERT OR IGNORE INTO knowledge_revocations(business_id, source_id, source_version, reason, authority, created_at) "
            "SELECT business_id, source_id, source_version, 'migrated revoked source', 'migration', updated_at "
            "FROM knowledge_sources WHERE status = 'revoked'"
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS channel_events (
                channel TEXT NOT NULL,
                external_event_id TEXT NOT NULL,
                business_id TEXT,
                conversation_id TEXT,
                status TEXT NOT NULL,
                reason TEXT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (channel, external_event_id)
            );
            CREATE TABLE IF NOT EXISTS outbound_ledger (
                message_key TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                provider_message_id TEXT,
                content_sha256 TEXT NOT NULL,
                state TEXT NOT NULL,
                started_at TEXT NOT NULL,
                sent_at TEXT
            );
            CREATE INDEX IF NOT EXISTS outbound_ledger_provider_idx
                ON outbound_ledger(business_id, conversation_id, provider_message_id);
            CREATE INDEX IF NOT EXISTS outbound_ledger_content_idx
                ON outbound_ledger(business_id, conversation_id, content_sha256, state);
            CREATE TABLE IF NOT EXISTS operating_modes (
                scope_key TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                mode TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                cohort TEXT NOT NULL,
                limits TEXT NOT NULL,
                evaluated_package_version TEXT,
                evaluated_package_fingerprint TEXT,
                evaluated_model TEXT,
                evaluated_backend TEXT,
                reason TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pilot_metrics (
                scope_key TEXT PRIMARY KEY,
                counters TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pilot_reservations (
                scope_key TEXT NOT NULL,
                reservation_key TEXT NOT NULL,
                estimated_cost REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (scope_key, reservation_key)
            );
            CREATE TABLE IF NOT EXISTS supervisor_reviews (
                review_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                package_version TEXT,
                state_version INTEGER,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS supervisor_settings (
                scope_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                policy TEXT NOT NULL DEFAULT 'optional',
                correction_limit INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_governance_events (
                event_id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_version TEXT,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                authority TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS privacy_audit (
                id TEXT PRIMARY KEY, business_id TEXT NOT NULL, pseudonym TEXT NOT NULL,
                operation TEXT NOT NULL, count INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            """
        )
        supervisor_columns = {row["name"] for row in db.execute("PRAGMA table_info(supervisor_settings)").fetchall()}
        if "policy" not in supervisor_columns:
            db.execute("ALTER TABLE supervisor_settings ADD COLUMN policy TEXT NOT NULL DEFAULT 'optional'")
        operating_mode_columns = {row["name"] for row in db.execute("PRAGMA table_info(operating_modes)").fetchall()}
        if "evaluated_package_fingerprint" not in operating_mode_columns:
            db.execute("ALTER TABLE operating_modes ADD COLUMN evaluated_package_fingerprint TEXT")
        try:
            db.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
                    title, content, content='knowledge_sources', content_rowid='rowid',
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TRIGGER IF NOT EXISTS sources_fts_insert AFTER INSERT ON knowledge_sources BEGIN
                    INSERT INTO sources_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS sources_fts_delete AFTER DELETE ON knowledge_sources BEGIN
                    INSERT INTO sources_fts(sources_fts, rowid, title, content)
                    VALUES ('delete', old.rowid, old.title, old.content);
                END;
                CREATE TRIGGER IF NOT EXISTS sources_fts_update AFTER UPDATE ON knowledge_sources BEGIN
                    INSERT INTO sources_fts(sources_fts, rowid, title, content)
                    VALUES ('delete', old.rowid, old.title, old.content);
                    INSERT INTO sources_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
                END;
                """
            )
            if version < 12:
                db.execute("INSERT INTO sources_fts(sources_fts) VALUES ('rebuild')")
        except sqlite3.OperationalError as exc:
            if "no such module: fts5" not in str(exc).lower():
                raise
        db.execute("PRAGMA user_version = %d" % DATABASE_SCHEMA_VERSION)


    def schema_version(self) -> int:
        with self.connect() as db:
            return int(db.execute("PRAGMA user_version").fetchone()[0])

    def fts5_available(self) -> bool:
        with self.connect() as db:
            return db.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'sources_fts' AND type = 'table'"
            ).fetchone() is not None

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

    def backup_to(self, destination: Union[Path, str]) -> Path:
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

    def restore_from(self, source: Union[Path, str], backup_current: Union[Path, str]) -> Dict[str, Any]:
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

    def get_business_version(self, business_id: str, version: int) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT version, payload, created_at FROM business_versions WHERE business_id = ? AND version = ?",
                (business_id, version),
            ).fetchone()
        if not row:
            return None
        return {"version": int(row["version"]), "created_at": row["created_at"], "package": self.loads(row["payload"])}

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

    def has_persisted_action(self, business_id: str, conversation_id: str, action_type: str) -> bool:
        """Check an action already committed by the conversation seam."""

        if not str(action_type).strip():
            raise ValueError("action_type não pode ser vazio")
        with self.connect() as db:
            rows = db.execute(
                "SELECT result FROM events WHERE business_id = ? AND conversation_id = ?",
                (business_id, conversation_id),
            ).fetchall()
        for row in rows:
            result = self.loads(row["result"])
            action = result.get("action") if isinstance(result, Mapping) else None
            if isinstance(action, Mapping) and str(action.get("type")) == str(action_type):
                return True
        return False

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
        now_value = datetime.fromisoformat(self.clock.now().replace("Z", "+00:00"))
        now = now_value.isoformat(timespec="seconds")
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT result FROM events WHERE business_id = ? AND conversation_id = ? AND event_id = ?",
                (business_id, conversation_id, event_id),
            ).fetchone()
            if existing:
                existing_result = self.loads(existing["result"])
                candidate_action = result.get("action") if isinstance(result.get("action"), Mapping) else None
                effect_key = str(candidate_action.get("effect_key", "")) if candidate_action else ""
                existing_action = existing_result.get("action") if isinstance(existing_result, Mapping) else None
                existing_state = existing_result.get("state") if isinstance(existing_result, Mapping) else None
                existing_pending = existing_state.get("pending") if isinstance(existing_state, Mapping) else None
                existing_operation = existing_state.get("operation") if isinstance(existing_state, Mapping) else None
                existing_trace = existing_result.get("trace", []) if isinstance(existing_result, Mapping) else []
                # A concurrent worker may have committed an explicit
                # in-progress action envelope rather than an action-less
                # result. Only those pending envelopes are repairable. A
                # confirmed action, human transfer, or unrelated action must
                # remain authoritative.
                existing_effect_pending = (
                    isinstance(existing_pending, Mapping)
                    and existing_pending.get("type") == "effect_in_progress"
                ) or (
                    isinstance(existing_operation, Mapping)
                    and existing_operation.get("status") in {"pending", "reserved"}
                ) or (
                    isinstance(existing_action, Mapping)
                    and existing_action.get("status") in {"pending", "in_progress", "reserved"}
                ) or any(
                    isinstance(item, Mapping)
                    and item.get("type") in {"checkout_in_progress", "proposal_in_progress"}
                    for item in existing_trace
                )
                # Two workers can interpret the same inbound event before
                # either one commits.  If the slower worker confirmed the
                # idempotent effect after the faster worker persisted an
                # ``effect_in_progress`` response, repair that durable event
                # atomically.  Otherwise a confirmed checkout could have
                # inventory reserved but no checkout response in the outbox.
                same_pending_action = (
                    isinstance(existing_action, Mapping)
                    and isinstance(candidate_action, Mapping)
                    and str(existing_action.get("type", "")) == str(candidate_action.get("type", ""))
                )
                if effect_key and (
                    not isinstance(existing_action, Mapping)
                    or (existing_effect_pending and same_pending_action)
                ):
                    effect_row = db.execute(
                        "SELECT kind, status, payload FROM effects WHERE effect_key = ?", (effect_key,)
                    ).fetchone()
                    expected_kind = {
                        "prepare_checkout": "checkout",
                        "prepare_proposal": "proposal",
                    }.get(str(candidate_action.get("type", "")))
                    if (
                        effect_row
                        and effect_row["status"] == "confirmed"
                        and expected_kind is not None
                        and str(effect_row["kind"]) == expected_kind
                    ):
                        effect_payload = self.loads(effect_row["payload"])
                        action_type = str(candidate_action.get("type", ""))
                        canonical_action = {
                            **dict(candidate_action),
                            **effect_payload,
                            "type": action_type,
                            "effect_key": effect_key,
                        }
                        conversation_row = db.execute(
                            "SELECT version, payload FROM conversations WHERE business_id = ? AND conversation_id = ?",
                            (business_id, conversation_id),
                        ).fetchone()
                        canonical_state = self.loads(conversation_row["payload"]) if conversation_row else dict(state)
                        current_version = int(conversation_row["version"]) if conversation_row else int(state.get("version", 0))
                        human_paused = (
                            canonical_state.get("responsible") == "human"
                            or canonical_state.get("status") == "human_paused"
                        )
                        if not human_paused:
                            operation_type = {
                                "prepare_checkout": "checkout",
                                "prepare_proposal": "proposal",
                            }.get(action_type, str((canonical_state.get("operation") or {}).get("type", effect_row["kind"])))
                            canonical_state["operation"] = {
                                "type": operation_type,
                                **effect_payload,
                                "status": "confirmed",
                                "effect_key": effect_key,
                            }
                            canonical_state["phase"] = "action_in_progress"
                            canonical_state["pending"] = None
                            canonical_state["version"] = current_version + 1
                            history = canonical_state.get("history")
                            if isinstance(history, list):
                                for entry in reversed(history):
                                    if isinstance(entry, dict) and str(entry.get("event_id")) == event_id:
                                        entry["response"] = result.get("response", "")
                                        entry["action"] = canonical_action
                                        break
                        canonical_result = {
                            **result,
                            "action": canonical_action,
                            "state": canonical_state,
                            "trace": list(result.get("trace", [])) + [{"type": "confirmed_effect_race_repaired"}],
                        }
                        if conversation_row and not human_paused:
                            db.execute(
                                "UPDATE conversations SET version = ?, payload = ?, updated_at = ? "
                                "WHERE business_id = ? AND conversation_id = ?",
                                (
                                    canonical_state["version"],
                                    self.dumps(canonical_state),
                                    now,
                                    business_id,
                                    conversation_id,
                                ),
                            )
                        elif not conversation_row and not human_paused:
                            db.execute(
                                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                                (
                                    business_id,
                                    conversation_id,
                                    canonical_state["version"],
                                    self.dumps(canonical_state),
                                    now,
                                ),
                            )
                        db.execute(
                            "UPDATE events SET result = ? WHERE business_id = ? AND conversation_id = ? AND event_id = ?",
                            (self.dumps(canonical_result), business_id, conversation_id, event_id),
                        )
                        repaired_outbox = dict(outbox_payload)
                        repaired_outbox["action"] = canonical_action
                        repaired_outbox.pop("defer_delivery", None)
                        outbox_row = db.execute(
                            "SELECT status FROM outbox WHERE message_key = ?", (message_key,)
                        ).fetchone()
                        if outbox_row is None:
                            if repaired_outbox.get("response") or repaired_outbox.get("action"):
                                db.execute(
                                    "INSERT INTO outbox(message_key, business_id, conversation_id, payload, status, created_at, "
                                    "attempts, available_at, leased_until, last_error, updated_at) "
                                    "VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, NULL, NULL, ?)",
                                    (
                                        message_key,
                                        business_id,
                                        conversation_id,
                                        self.dumps(repaired_outbox),
                                        now,
                                        now,
                                        now,
                                    ),
                                )
                        elif outbox_row["status"] == "pending":
                            db.execute(
                                "UPDATE outbox SET payload = ?, updated_at = ? WHERE message_key = ? AND status = 'pending'",
                                (self.dumps(repaired_outbox), now, message_key),
                            )
                        return "duplicate", canonical_result
                return "duplicate", existing_result
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
            if (outbox_payload.get("response") or outbox_payload.get("action")) and not outbox_payload.get("defer_delivery"):
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
        message_key: Optional[str] = None,
        outbox_payload: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Atomically audit a stale response and optional delivery intent.

        A stale worker may have completed an idempotent effect before losing
        the conversation CAS.  The reconciliation notice must therefore be
        committed with the audit event, or it can disappear between workers.
        """

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
            envelope = dict(outbox_payload or {})
            if message_key and (envelope.get("response") or envelope.get("action")) and not envelope.get("defer_delivery"):
                db.execute(
                    "INSERT OR IGNORE INTO outbox(message_key, business_id, conversation_id, payload, status, created_at, "
                    "attempts, available_at, leased_until, last_error, updated_at) "
                    "VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, NULL, NULL, ?)",
                    (message_key, business_id, conversation_id, self.dumps(envelope), now, now, now),
                )
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                (business_id, conversation_id, event_id, self.dumps(event), self.dumps(result), now),
            )
            return "committed", None

    def reserve_effect(self, effect_key: str, kind: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        now_value = datetime.now(timezone.utc)
        now = now_value.isoformat(timespec="seconds")
        reservation = {
            **payload,
            "reservation_id": uuid.uuid4().hex,
            "reservation_expires_at": (now_value + timedelta(minutes=2)).isoformat(timespec="seconds"),
        }
        with self._lock, self.connect() as db:
            # The unique key is the final arbiter across processes.  BEGIN
            # IMMEDIATE turns the read/insert pair into one serialized
            # reservation instead of allowing two workers to observe absence.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
            if row:
                stored = self.loads(row["payload"])
                expired = row["status"] == "reserved" and reservation_expired(stored, now_value)
                return False, {
                    **stored,
                    "status": row["status"],
                    "reservation_in_progress": row["status"] == "reserved" and not expired,
                    "reservation_expired": expired,
                }
            try:
                db.execute(
                    "INSERT INTO effects VALUES (?, ?, ?, ?, ?, ?)",
                    (effect_key, kind, "reserved", self.dumps(reservation), now, now),
                )
            except sqlite3.IntegrityError:
                row = db.execute("SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)).fetchone()
                if row:
                    stored = self.loads(row["payload"])
                    expired = row["status"] == "reserved" and reservation_expired(stored, now_value)
                    return False, {
                        **stored,
                        "status": row["status"],
                        "reservation_in_progress": row["status"] == "reserved" and not expired,
                        "reservation_expired": expired,
                    }
                raise
            return True, {**reservation, "status": "reserved"}

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
        now_value = datetime.now(timezone.utc)
        now = now_value.isoformat(timespec="seconds")
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT status, payload FROM effects WHERE effect_key = ?", (effect_key,)
            ).fetchone()
            if existing:
                stored = self.loads(existing["payload"])
                expired = existing["status"] == "reserved" and reservation_expired(stored, now_value)
                return "existing", {
                    **stored,
                    "status": existing["status"],
                    "reservation_in_progress": existing["status"] == "reserved" and not expired,
                    "reservation_expired": expired,
                }
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
                "reservation_id": uuid.uuid4().hex,
                "reservation_expires_at": (now_value + timedelta(minutes=2)).isoformat(timespec="seconds"),
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
                    pending = conversation_state.get("pending") or {}
                    awaiting_reconciliation = (
                        operation.get("status") == "unknown"
                        or pending.get("type") == "post_effect_correction"
                    ) and (
                        operation.get("effect_key") == effect_key
                        or operation.get("quote_id") == payload.get("quote_id")
                        or pending.get("effect_key") == effect_key
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

    def claim_outbox(
        self, limit: int = 10, lease_seconds: int = 60, *, now: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lease eligible messages to one delivery worker."""

        if limit < 1 or limit > 100:
            raise ValueError("limit deve estar entre 1 e 100")
        if lease_seconds < 1 or lease_seconds > 3600:
            raise ValueError("lease_seconds deve estar entre 1 e 3600")
        now_value = datetime.fromisoformat(now.replace("Z", "+00:00")) if now else datetime.now(timezone.utc)
        now_text = now_value.isoformat(timespec="seconds")
        leased_until = (now_value + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
        lease_owner = "lease-%s" % uuid.uuid4().hex
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
                    "UPDATE outbox SET status = 'processing', attempts = attempts + 1, leased_until = ?, lease_owner = ?, updated_at = ? "
                    "WHERE message_key = ? AND status = 'pending'",
                    (leased_until, lease_owner, now_text, key),
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
            "lease_owner": row["lease_owner"],
            "last_error": row["last_error"],
        }

    def begin_outbound(self, item: Mapping[str, Any]) -> bool:
        """Record a public Chatwoot send before crossing the provider boundary."""

        key = str(item.get("message_key", ""))
        owner = str(item.get("lease_owner", ""))
        business_id = str(item.get("business_id", ""))
        conversation_id = str(item.get("conversation_id", ""))
        content = str(item.get("response", ""))
        if not all((key, owner, business_id, conversation_id, content)):
            return False
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = self.clock.now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT business_id, conversation_id, leased_until FROM outbox "
                "WHERE message_key = ? AND status = 'processing' AND lease_owner = ?",
                (key, owner),
            ).fetchone()
            if not row or row["business_id"] != business_id or row["conversation_id"] != conversation_id:
                return False
            if not row["leased_until"] or normalize_iso_datetime(row["leased_until"]) <= normalize_iso_datetime(now):
                return False
            cursor = db.execute(
                "INSERT INTO outbound_ledger(message_key, business_id, conversation_id, provider_message_id, "
                "content_sha256, state, started_at, sent_at) VALUES (?, ?, ?, NULL, ?, 'in_flight', ?, NULL) "
                "ON CONFLICT(message_key) DO UPDATE SET content_sha256 = excluded.content_sha256, "
                "state = 'in_flight', started_at = excluded.started_at "
                "WHERE outbound_ledger.state = 'failed'",
                (key, business_id, conversation_id, content_hash, now),
            )
            return cursor.rowcount == 1

    def match_outbound(
        self, business_id: str, conversation_id: str, provider_message_id: str, content: str
    ) -> Optional[str]:
        """Return id/content match for an authenticated outgoing webhook."""

        with self.connect() as db:
            if provider_message_id:
                row = db.execute(
                    "SELECT 1 FROM outbound_ledger WHERE business_id = ? AND conversation_id = ? "
                    "AND provider_message_id = ? AND state = 'sent' LIMIT 1",
                    (business_id, conversation_id, provider_message_id),
                ).fetchone()
                if row:
                    return "id"
            if not content:
                return None
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            rows = db.execute(
                "SELECT started_at FROM outbound_ledger WHERE business_id = ? AND conversation_id = ? "
                "AND content_sha256 = ? AND state = 'in_flight'",
                (business_id, conversation_id, content_hash),
            ).fetchall()
        now = datetime.fromisoformat(self.clock.now().replace("Z", "+00:00"))
        for row in rows:
            try:
                started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            if 0 <= (now - started).total_seconds() <= 120:
                return "content"
        return None

    def ack_outbox(
        self, message_key: str, *, lease_owner: Optional[str] = None, provider_message_id: Optional[str] = None
    ) -> bool:
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            owner = lease_owner
            if owner is None:
                # The owner-less form is an operator/CLI compatibility path.
                # Resolve the current owner inside the same transaction; a
                # delivery worker always supplies its captured owner token.
                row = db.execute(
                    "SELECT lease_owner FROM outbox WHERE message_key = ? AND status = 'processing'",
                    (message_key,),
                ).fetchone()
                owner = row["lease_owner"] if row else None
            if not owner:
                return False
            now = self.clock.now()
            cursor = db.execute(
                "UPDATE outbox SET status = 'sent', leased_until = NULL, lease_owner = NULL, last_error = NULL, updated_at = ? "
                "WHERE message_key = ? AND status = 'processing' AND lease_owner = ?",
                (now, message_key, owner),
            )
            if cursor.rowcount == 1 and provider_message_id:
                db.execute(
                    "UPDATE outbound_ledger SET provider_message_id = ?, state = 'sent', sent_at = ? "
                    "WHERE message_key = ? AND state = 'in_flight'",
                    (str(provider_message_id), now, message_key),
                )
            return cursor.rowcount == 1

    def nack_outbox(
        self,
        message_key: str,
        error: str,
        *,
        max_attempts: int = 5,
        delay_seconds: int = 30,
        lease_owner: Optional[str] = None,
    ) -> str:
        if not error.strip():
            raise ValueError("error não pode ser vazio")
        if max_attempts < 1 or delay_seconds < 0:
            raise ValueError("parâmetros de retry inválidos")
        now = datetime.now(timezone.utc)
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT attempts, status, lease_owner FROM outbox WHERE message_key = ?", (message_key,)
            ).fetchone()
            owner = lease_owner
            if owner is None and row:
                owner = row["lease_owner"]
            if not row or row["status"] != "processing" or not owner or row["lease_owner"] != owner:
                raise ValueError("mensagem não está em processamento: %s" % message_key)
            status = "dead_letter" if int(row["attempts"]) >= max_attempts else "pending"
            available_at = (now + timedelta(seconds=delay_seconds)).isoformat(timespec="seconds")
            db.execute(
                "UPDATE outbox SET status = ?, available_at = ?, leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ? AND status = 'processing' AND lease_owner = ?",
                (status, available_at, error[:2000], now.isoformat(timespec="seconds"), message_key, owner),
            )
            db.execute(
                "UPDATE outbound_ledger SET state = 'failed' WHERE message_key = ? AND state = 'in_flight'",
                (message_key,),
            )
            return status

    def confirm_outbox_lease(
        self, message_key: str, lease_owner: Optional[str], *, now: Optional[str] = None
    ) -> bool:
        """Confirm that a worker still owns an unexpired delivery lease.

        This is deliberately a separate, cheap transaction immediately before
        a provider call.  It closes the common stale-worker window; the
        provider's own idempotency contract is still required for the tiny
        check-to-network-call interval.
        """

        if not lease_owner:
            return False
        now_text = now or utc_now()
        with self._lock, self.connect() as db:
            row = db.execute(
                "SELECT leased_until FROM outbox WHERE message_key = ? AND status = 'processing' AND lease_owner = ?",
                (message_key, lease_owner),
            ).fetchone()
        if not row or not row["leased_until"]:
            return False
        try:
            return datetime.fromisoformat(str(row["leased_until"]).replace("Z", "+00:00")) > datetime.fromisoformat(
                now_text.replace("Z", "+00:00")
            )
        except ValueError:
            return False

    def reconcile_outbox(
        self,
        message_key: str,
        resolution: str,
        details: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Settle an unknown delivery without putting it back on the send queue."""

        if resolution not in {"sent", "cancelled", "dead_letter"}:
            raise ValueError("resolução de outbox deve ser sent, cancelled ou dead_letter")
        if details is not None and not isinstance(details, Mapping):
            raise ValueError("details precisa ser um objeto")
        details = dict(details or {})
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM outbox WHERE message_key = ?", (message_key,)).fetchone()
            if not row:
                raise ValueError("mensagem não encontrada: %s" % message_key)
            if row["status"] not in {"unknown", resolution}:
                raise ValueError("mensagem não está desconhecida: %s" % row["status"])
            payload = self.loads(row["payload"])
            provider = details.get("provider")
            if provider is not None and not isinstance(provider, Mapping):
                raise ValueError("provider precisa ser um objeto")
            payload["reconciliation"] = {
                "resolution": resolution,
                "provider": dict(provider or {}),
                "reason": str(details.get("reason", "operator reconciliation"))[:2000],
                "at": now,
            }
            db.execute(
                "UPDATE outbox SET status = ?, payload = ?, leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ? AND status IN ('unknown', ?)",
                (
                    resolution,
                    self.dumps(payload),
                    str(details.get("reason", "reconciled"))[:2000],
                    now,
                    message_key,
                    resolution,
                ),
            )
            return {
                **self._outbox_row(row),
                "status": resolution,
                "reconciliation": payload["reconciliation"],
            }

    def recover_expired_outbox(self, *, now: Optional[str] = None) -> int:
        now = now or utc_now()
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = 'delivery lease expired; delivery outcome is unknown', "
                "available_at = ?, updated_at = ? WHERE status = 'processing' AND leased_until <= ?",
                (now, now, now),
            )
            return cursor.rowcount

    def cancel_followups(self, business_id: str, conversation_id: str) -> int:
        with self._lock, self.connect() as db:
            now = utc_now()
            pending = db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, lease_owner = NULL, last_error = 'cancelled follow-up', updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'followup:%' AND status = 'pending'",
                (now, business_id, conversation_id),
            )
            processing = db.execute(
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = 'follow-up cancelled while delivery outcome was unknown', updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'followup:%' AND status = 'processing'",
                (now, business_id, conversation_id),
            )
            return pending.rowcount + processing.rowcount

    def cancel_outbox_message(self, message_key: str, reason: str, *, lease_owner: Optional[str] = None) -> bool:
        if not reason.strip():
            raise ValueError("reason não pode ser vazio")
        with self._lock, self.connect() as db:
            query = (
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ? AND status IN ('pending', 'processing')"
            )
            parameters: Tuple[Any, ...] = (reason[:2000], utc_now(), message_key)
            if lease_owner is not None:
                query += " AND lease_owner = ?"
                parameters += (lease_owner,)
            cursor = db.execute(query, parameters)
            return cursor.rowcount == 1

    def close_outbox_window(self, item: Mapping[str, Any], *, lease_owner: str) -> bool:
        """Close one public intent and queue its attendant note in one transaction."""
        key = str(item["message_key"])
        now = self.clock.now()
        note_key = "window-note:%s" % key
        note = {
            "channel": "chatwoot",
            "channel_kind": "whatsapp",
            "response": "Resposta não enviada: janela de 24 h encerrada",
            "action": {"type": "private_note"},
            "private": True,
        }
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            closed = db.execute(
                "UPDATE outbox SET status = 'window_closed', leased_until = NULL, lease_owner = NULL, "
                "last_error = 'window_closed', updated_at = ? "
                "WHERE message_key = ? AND status = 'processing' AND lease_owner = ?",
                (now, key, lease_owner),
            )
            if closed.rowcount != 1:
                return False
            db.execute(
                "INSERT OR IGNORE INTO outbox(message_key, business_id, conversation_id, payload, status, created_at, "
                "attempts, available_at, leased_until, last_error, updated_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, NULL, NULL, ?)",
                (note_key, item["business_id"], item["conversation_id"], self.dumps(note), now, now, now),
            )
            return True

    def mark_outbox_unknown(
        self, message_key: str, provider_result: Mapping[str, Any], *, lease_owner: Optional[str] = None
    ) -> bool:
        with self._lock, self.connect() as db:
            query = (
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ? AND status = 'processing'"
            )
            parameters: Tuple[Any, ...] = (
                self.dumps(
                    {"provider_status": provider_result.get("status"), "provider_id": provider_result.get("provider_id")}
                ),
                utc_now(),
                message_key,
            )
            if lease_owner is not None:
                query += " AND lease_owner = ?"
                parameters += (lease_owner,)
            cursor = db.execute(query, parameters)
            return cursor.rowcount == 1

    def mark_outbox_observed(
        self, message_key: str, reason: str = "observation mode", *, lease_owner: Optional[str] = None
    ) -> bool:
        if not reason.strip():
            raise ValueError("reason não pode ser vazio")
        with self._lock, self.connect() as db:
            query = (
                "UPDATE outbox SET status = 'observed', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE message_key = ? AND status = 'processing'"
            )
            parameters: Tuple[Any, ...] = (reason[:2000], utc_now(), message_key)
            if lease_owner is not None:
                query += " AND lease_owner = ?"
                parameters += (lease_owner,)
            cursor = db.execute(query, parameters)
            return cursor.rowcount == 1

    def cancel_pending_deliveries(self, business_id: str, conversation_id: str, reason: str) -> int:
        """Cancel queued event replies before a human takeover or refusal.

        The current event is committed after the decision, so this operation only
        touches earlier responses. Keeping the audit rows while changing their
        delivery state makes the cancellation observable without sending a
        repeated warning to the buyer.
        """

        if not reason.strip():
            raise ValueError("reason não pode ser vazio")
        with self._lock, self.connect() as db:
            now = utc_now()
            pending = db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'event:%' AND status = 'pending'",
                (reason[:2000], now, business_id, conversation_id),
            )
            processing = db.execute(
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'event:%' AND status = 'processing'",
                ("%s; delivery outcome is unknown" % reason[:1900], now, business_id, conversation_id),
            )
            return pending.rowcount + processing.rowcount

    def cancel_followup(self, business_id: str, conversation_id: str, task_id: str) -> int:
        with self._lock, self.connect() as db:
            now = utc_now()
            message_key = durable_key("followup", business_id, conversation_id, task_id)
            pending = db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, lease_owner = NULL, last_error = 'cancelled follow-up', updated_at = ? "
                "WHERE message_key = ? AND business_id = ? AND conversation_id = ? AND status = 'pending'",
                (now, message_key, business_id, conversation_id),
            )
            processing = db.execute(
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = 'follow-up cancelled while delivery outcome was unknown', updated_at = ? "
                "WHERE message_key = ? AND business_id = ? AND conversation_id = ? AND status = 'processing'",
                (now, message_key, business_id, conversation_id),
            )
            return pending.rowcount + processing.rowcount

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
            self._put_source_db(db, source)

    @staticmethod
    def _put_source_db(db: sqlite3.Connection, source: Mapping[str, Any]) -> None:
        content = str(source["content"])
        content_hash = str(source["content_hash"])
        computed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if content_hash != computed_hash:
            raise ValueError("hash de conteúdo da fonte não corresponde ao documento")
        source_status = str(source.get("status", "approved"))
        if source_status not in {"approved", "revoked", "pending"}:
            raise ValueError("status de fonte desconhecido; não será aprovado automaticamente")
        valid_from = source.get("valid_from")
        valid_until = source.get("valid_until")
        for field, value in (("valid_from", valid_from), ("valid_until", valid_until)):
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("%s da fonte precisa ser ISO-8601" % field)
                try:
                    normalized = normalize_iso_datetime(value)
                except ValueError as exc:
                    raise ValueError("%s da fonte não é uma data válida" % field) from exc
                if field == "valid_from":
                    valid_from = normalized
                else:
                    valid_until = normalized
        if valid_from and valid_until:
            if normalize_iso_datetime(valid_from) >= normalize_iso_datetime(valid_until):
                raise ValueError("vigência da fonte tem intervalo inválido")
        existing = db.execute(
            "SELECT content_hash, review_status, status, active FROM knowledge_sources "
            "WHERE business_id = ? AND source_id = ? AND source_version = ?",
            (source["business_id"], source["source_id"], source["source_version"]),
        ).fetchone()
        if existing and str(existing["content_hash"]) != content_hash:
            raise ValueError("revisão de fonte é imutável; use uma nova source_version")
        revoked = db.execute(
            "SELECT 1 FROM knowledge_revocations WHERE business_id = ? AND source_id = ? "
            "AND (source_version IS NULL OR source_version = ?) LIMIT 1",
            (source["business_id"], source["source_id"], source["source_version"]),
        ).fetchone()
        status = "revoked" if revoked else source_status
        review_status = str(
            source.get(
                "review_status",
                existing["review_status"] if existing and existing["review_status"] else "approved",
            )
        )
        if review_status not in {"approved", "pending_review"}:
            raise ValueError("review_status de fonte inválido")
        legacy_migration = source.get("origin") == "farol-artifact-legacy-migration"
        source_active = bool(source.get("active", True))
        if legacy_migration and existing and existing["review_status"] == "approved" and not revoked:
            # Reimporting an unchanged legacy revision cannot undo an owner's
            # explicit review or active selection.
            review_status = "approved"
            if source_status == "pending":
                status = "approved"
            source_active = bool(existing["active"])
        db.execute(
            "INSERT INTO knowledge_sources(business_id, source_id, source_version, title, content, locator, status, origin, content_hash, backend, scope, audience, subject, valid_from, valid_until, active, generation, review_status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(business_id, source_id, source_version) DO UPDATE SET title=excluded.title, content=excluded.content, locator=excluded.locator, status=excluded.status, origin=excluded.origin, content_hash=excluded.content_hash, backend=excluded.backend, scope=excluded.scope, audience=excluded.audience, subject=excluded.subject, valid_from=excluded.valid_from, valid_until=excluded.valid_until, active=excluded.active, generation=excluded.generation, review_status=excluded.review_status, updated_at=excluded.updated_at",
            (
                source["business_id"],
                source["source_id"],
                source["source_version"],
                source.get("title", source["source_id"]),
                content,
                source.get("locator", source["source_id"]),
                status,
                source.get("origin", "local"),
                source["content_hash"],
                source.get("backend", "sqlite-farol-v1"),
                source.get("scope", ""),
                source.get("audience", ""),
                source.get("subject", ""),
                valid_from,
                valid_until,
                1 if source_active else 0,
                source.get("generation"),
                review_status,
                utc_now(),
            ),
        )
        if source_status == "revoked" and not revoked:
            db.execute(
                "INSERT OR IGNORE INTO knowledge_revocations VALUES (?, ?, ?, ?, ?, ?)",
                (
                    source["business_id"],
                    source["source_id"],
                    source["source_version"],
                    "source imported as revoked",
                    str(source.get("origin", "package")),
                    utc_now(),
                ),
            )

    def put_sources_atomic(
        self,
        sources: List[Mapping[str, Any]],
        *,
        generation: Optional[str] = None,
        revocations: Optional[List[Mapping[str, Any]]] = None,
        deactivate_keys: Optional[List[Mapping[str, Any]]] = None,
    ) -> int:
        if not sources and not revocations and not deactivate_keys:
            return 0
        governance_events = []
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for previous in deactivate_keys or []:
                business_id = str(previous.get("business_id", ""))
                source_id = str(previous.get("source_id", ""))
                source_version = str(previous.get("source_version", ""))
                if not business_id or not source_id or not source_version:
                    continue
                db.execute(
                    "UPDATE knowledge_sources SET active = 0, updated_at = ? "
                    "WHERE business_id = ? AND source_id = ? AND source_version = ?",
                    (utc_now(), business_id, source_id, source_version),
                )
            if generation:
                # A promoted Farol generation is a snapshot.  Keep historical
                # rows for audit, but remove older artifact generations from
                # the active retrieval set before staging the new one.
                business_ids = sorted({str(source["business_id"]) for source in sources})
                for business_id in business_ids:
                    db.execute(
                        "UPDATE knowledge_sources SET active = 0, updated_at = ? "
                        "WHERE business_id = ? AND backend = 'farol-artifact-v1' "
                        "AND (generation IS NULL OR generation <> ?)",
                        (utc_now(), business_id, generation),
                    )
            active_scopes = {
                (
                    str(source["business_id"]),
                    str(source["source_id"]),
                    str(source.get("scope", "")),
                    str(source.get("audience", "")),
                    str(source.get("subject", "")),
                )
                for source in sources
                if bool(source.get("active", True)) and source.get("status", "approved") == "approved"
            }
            for business_id, source_id, scope, audience, subject in active_scopes:
                db.execute(
                    "UPDATE knowledge_sources SET active = 0, updated_at = ? WHERE business_id = ? AND source_id = ? AND scope = ? AND audience = ? AND subject = ?",
                    (utc_now(), business_id, source_id, scope, audience, subject),
                )
            for source in sources:
                value = dict(source)
                if generation and not value.get("generation"):
                    value["generation"] = generation
                self._put_source_db(db, value)
            for revocation in revocations or []:
                business_id = str(revocation.get("business_id", ""))
                source_id = str(revocation.get("source_id", ""))
                source_version = revocation.get("source_version")
                if not business_id or not source_id:
                    continue
                revocation_cursor = db.execute(
                    "INSERT OR IGNORE INTO knowledge_revocations VALUES (?, ?, ?, ?, ?, ?)",
                    (business_id, source_id, str(source_version) if source_version is not None else None, "upstream revocation", "farol-artifact", utc_now()),
                )
                if source_version is None:
                    db.execute(
                        "UPDATE knowledge_sources SET status = 'revoked', updated_at = ? WHERE business_id = ? AND source_id = ?",
                        (utc_now(), business_id, source_id),
                    )
                else:
                    db.execute(
                        "UPDATE knowledge_sources SET status = 'revoked', updated_at = ? WHERE business_id = ? AND source_id = ? AND source_version = ?",
                        (utc_now(), business_id, source_id, str(source_version)),
                    )
                if revocation_cursor.rowcount == 1:
                    governance_events.append((business_id, source_id, source_version))
        for business_id, source_id, source_version in governance_events:
            self.record_knowledge_governance_event(
                business_id,
                source_id,
                source_version,
                "upstream_revoke",
                "upstream revocation",
                "farol-artifact",
            )
        return len(sources)

    def revoke_source(self, business_id: str, source_id: str, source_version: Optional[str] = None) -> int:
        if not str(business_id).strip() or not str(source_id).strip():
            raise ValueError("revogação exige negócio e fonte")
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO knowledge_revocations VALUES (?, ?, ?, ?, ?, ?)",
                (business_id, source_id, source_version, "revoked by owner", "owner", utc_now()),
            )
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
            count = cursor.rowcount
        self.record_knowledge_governance_event(
            business_id,
            source_id,
            source_version,
            "revoke",
            "revoked by owner",
            "owner",
        )
        return count

    def reapprove_source(self, business_id: str, source_id: str, source_version: Optional[str], reason: str) -> int:
        """Explicitly reverse a revocation; importing alone never does this."""

        if not reason.strip():
            raise ValueError("reaprovação exige motivo")
        with self._lock, self.connect() as db:
            if source_version is None:
                rows = db.execute(
                    "SELECT authority FROM knowledge_revocations WHERE business_id = ? AND source_id = ? AND source_version IS NULL",
                    (business_id, source_id),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT authority FROM knowledge_revocations WHERE business_id = ? AND source_id = ? "
                    "AND (source_version = ? OR source_version IS NULL)",
                    (business_id, source_id, source_version),
                ).fetchall()
            if any(str(row["authority"]) != "owner" for row in rows):
                raise ValueError("revogação upstream exige nova decisão da autoridade de origem")
            if source_version is None:
                cursor = db.execute(
                    "DELETE FROM knowledge_revocations WHERE business_id = ? AND source_id = ? AND source_version IS NULL",
                    (business_id, source_id),
                )
                source_filter = (business_id, source_id)
                rows_to_update = db.execute(
                    "SELECT source_version FROM knowledge_sources WHERE business_id = ? AND source_id = ?",
                    source_filter,
                ).fetchall()
            else:
                cursor = db.execute(
                    "DELETE FROM knowledge_revocations WHERE business_id = ? AND source_id = ? AND source_version = ?",
                    (business_id, source_id, source_version),
                )
                rows_to_update = db.execute(
                    "SELECT source_version FROM knowledge_sources WHERE business_id = ? AND source_id = ? AND source_version = ?",
                    (business_id, source_id, source_version),
                ).fetchall()
            changed = 0
            for row in rows_to_update:
                revision = str(row["source_version"])
                remaining = db.execute(
                    "SELECT 1 FROM knowledge_revocations WHERE business_id = ? AND source_id = ? "
                    "AND (source_version IS NULL OR source_version = ?) LIMIT 1",
                    (business_id, source_id, revision),
                ).fetchone()
                if remaining:
                    continue
                update = db.execute(
                    "UPDATE knowledge_sources SET status = 'approved', updated_at = ? WHERE business_id = ? "
                    "AND source_id = ? AND source_version = ? AND status = 'revoked'",
                    (utc_now(), business_id, source_id, revision),
                )
                changed += update.rowcount
            count = cursor.rowcount
        if count:
            self.record_knowledge_governance_event(
                business_id,
                source_id,
                source_version,
                "reapprove",
                reason,
                "owner",
            )
        return count if count else changed

    def record_knowledge_governance_event(
        self,
        business_id: str,
        source_id: str,
        source_version: Optional[str],
        action: str,
        reason: str,
        authority: str,
    ) -> Dict[str, Any]:
        if not all(str(value).strip() for value in (business_id, source_id, action, reason, authority)):
            raise ValueError("evento de governança incompleto")
        created_at = utc_now()
        event_id = durable_key(
            "knowledge-governance",
            str(business_id),
            str(source_id),
            str(source_version or "*"),
            str(action),
            created_at,
            uuid.uuid4().hex,
        )
        value = {
            "event_id": event_id,
            "business_id": str(business_id),
            "source_id": str(source_id),
            "source_version": str(source_version) if source_version is not None else None,
            "action": str(action),
            "reason": str(reason)[:2000],
            "authority": str(authority),
            "created_at": created_at,
        }
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO knowledge_governance_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(value[key] for key in ("event_id", "business_id", "source_id", "source_version", "action", "reason", "authority", "created_at")),
            )
        return value

    def list_governance_events(self, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as db:
            if business_id is None:
                rows = db.execute("SELECT * FROM knowledge_governance_events ORDER BY created_at, rowid").fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM knowledge_governance_events WHERE business_id = ? ORDER BY created_at, rowid",
                    (business_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def search_sources(
        self,
        business_id: str,
        query: str,
        max_results: int = 5,
        *,
        as_of: Optional[str] = None,
        audience: str = "",
        scope: str = "",
        subject: str = "",
    ) -> List[Dict[str, Any]]:
        try:
            as_of = normalize_iso_datetime(as_of or self.clock.now())
        except ValueError:
            return []
        tokens = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
        if not tokens or max_results <= 0:
            return []
        requested_topics = _requested_topics(query)
        with self.connect() as db:
            fts_available = db.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'sources_fts' AND type = 'table'"
            ).fetchone() is not None
            filters = (
                "s.business_id = ? AND s.status = 'approved' AND s.review_status = 'approved' "
                "AND s.active = 1 AND (s.valid_from IS NULL OR s.valid_from <= ?) "
                "AND (s.valid_until IS NULL OR s.valid_until > ?) "
                "AND NOT EXISTS (SELECT 1 FROM knowledge_revocations r WHERE r.business_id = s.business_id "
                "AND r.source_id = s.source_id AND (r.source_version IS NULL OR r.source_version = s.source_version))"
            )
            params: List[Any] = [business_id, as_of, as_of]
            if audience:
                filters += " AND s.audience = ?"
                params.append(audience)
            if scope:
                filters += " AND s.scope = ?"
                params.append(scope)
            if subject:
                filters += " AND s.subject = ?"
                params.append(subject)
            if fts_available:
                match = " OR ".join('"%s"' % token for token in tokens)
                rows = db.execute(
                    "SELECT s.*, -bm25(sources_fts, 2.0, 1.0) AS rank_score "
                    "FROM sources_fts JOIN knowledge_sources s ON s.rowid = sources_fts.rowid "
                    "WHERE sources_fts MATCH ? AND " + filters + " ORDER BY bm25(sources_fts, 2.0, 1.0) "
                    "LIMIT ?",
                    (match, *params, max(max_results * 10, 50) if requested_topics else max_results),
                ).fetchall()
            else:
                rows = db.execute("SELECT s.*, 0.0 AS rank_score FROM knowledge_sources s WHERE " + filters, params).fetchall()
        query_tokens = {_plain_text(token) for token in tokens}
        hits = []
        for row in rows:
            content = row["content"]
            plain_haystack = _plain_text(row["title"] + " " + content)
            if requested_topics and not any(any(term in plain_haystack for term in topic) for topic in requested_topics):
                continue
            if fts_available:
                score = float(row["rank_score"])
            else:
                overlap = sum(1 for token in query_tokens if token in plain_haystack)
                score = float(overlap) + (0.5 if _plain_text(query) in plain_haystack else 0.0)
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
                    "scope": row["scope"],
                    "audience": row["audience"],
                    "subject": row["subject"],
                    "valid_from": row["valid_from"],
                    "valid_until": row["valid_until"],
                    "active": bool(row["active"]),
                    "generation": row["generation"],
                    "review_status": row["review_status"],
                }
            )
        if not fts_available:
            hits.sort(key=lambda item: (-item["score"], item["source_id"], item["source_version"]))
        return hits[:max_results]

    def list_sources(self, business_id: str) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM knowledge_sources WHERE business_id = ? ORDER BY source_id, source_version",
                (business_id,),
            ).fetchall()
        return [
            {
                "evidence_id": "%s:%s:%s" % (business_id, row["source_id"], row["source_version"]),
                "business_id": row["business_id"],
                "source_id": row["source_id"],
                "source_version": row["source_version"],
                "title": row["title"],
                "locator": row["locator"],
                "status": row["status"],
                "origin": row["origin"],
                "backend": row["backend"],
                "scope": row["scope"],
                "audience": row["audience"],
                "subject": row["subject"],
                "valid_from": row["valid_from"],
                "valid_until": row["valid_until"],
                "active": bool(row["active"]),
                "generation": row["generation"],
                "review_status": row["review_status"],
            }
            for row in rows
        ]

    def list_pending_source_reviews(self, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List migrated source rows that require an explicit owner review."""

        with self.connect() as db:
            if business_id:
                rows = db.execute(
                    "SELECT * FROM knowledge_sources WHERE business_id = ? AND review_status = 'pending_review' "
                    "ORDER BY source_id, source_version",
                    (business_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM knowledge_sources WHERE review_status = 'pending_review' "
                    "ORDER BY business_id, source_id, source_version"
                ).fetchall()
        return [
            {
                "evidence_id": "%s:%s:%s" % (row["business_id"], row["source_id"], row["source_version"]),
                "business_id": row["business_id"],
                "source_id": row["source_id"],
                "source_version": row["source_version"],
                "title": row["title"],
                "locator": row["locator"],
                "status": row["status"],
                "origin": row["origin"],
                "backend": row["backend"],
                "review_status": row["review_status"],
            }
            for row in rows
        ]

    def review_source(self, business_id: str, source_id: str, source_version: str, reason: str, *, authority: str = "owner") -> bool:
        """Promote a migrated source only through an explicit audited review."""

        if not all(str(value).strip() for value in (business_id, source_id, source_version, reason, authority)):
            raise ValueError("revisão de fonte migrada incompleta")
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE knowledge_sources SET review_status = 'approved', status = CASE WHEN status = 'pending' THEN 'approved' ELSE status END, active = 1, updated_at = ? "
                "WHERE business_id = ? AND source_id = ? AND source_version = ? AND review_status = 'pending_review'",
                (utc_now(), business_id, source_id, source_version),
            )
        if cursor.rowcount:
            self.record_knowledge_governance_event(
                business_id, source_id, source_version, "legacy_review", reason, authority
            )
        return cursor.rowcount == 1

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

    def save_inbound_message(self, event: Mapping[str, Any], received_at: str) -> bool:
        with self._lock, self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO inbound_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', NULL)",
                    (
                        str(event["business_id"]),
                        str(event["conversation_id"]),
                        str(event["event_id"]),
                        str(event["contact_id"]),
                        str(event.get("channel", "cli")),
                        str(event["text"]),
                        self.dumps(dict(event)),
                        received_at,
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_queued_inbound(self) -> List[Dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                # rowid is the durable insertion sequence of this table.  A
                # provider may timestamp several messages to the same second;
                # the external message id is not an ordering signal.
                "SELECT rowid AS durable_order, * FROM inbound_messages WHERE status = 'queued' ORDER BY received_at, durable_order"
            ).fetchall()
        return [
            {
                "business_id": row["business_id"],
                "conversation_id": row["conversation_id"],
                "message_id": row["message_id"],
                "contact_id": row["contact_id"],
                "channel": row["channel"],
                "text": row["text"],
                "event": self.loads(row["event_payload"]),
                "received_at": row["received_at"],
                "status": row["status"],
                "durable_order": int(row["durable_order"]),
            }
            for row in rows
        ]

    def latest_buyer_message(self, business_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Return the latest durably admitted Chatwoot buyer message for a conversation."""
        with self.connect() as db:
            row = db.execute(
                "SELECT received_at, event_payload FROM inbound_messages "
                "WHERE business_id = ? AND conversation_id = ? AND channel = 'chatwoot' "
                "ORDER BY received_at DESC, rowid DESC LIMIT 1",
                (business_id, conversation_id),
            ).fetchone()
        return {"received_at": row["received_at"], "event": self.loads(row["event_payload"])} if row else None

    def buyer_window_open(self, business_id: str, conversation_id: str) -> bool:
        latest = self.latest_buyer_message(business_id, conversation_id)
        if latest is None:
            return False
        received_at = datetime.fromisoformat(str(latest["received_at"]).replace("Z", "+00:00"))
        now = datetime.fromisoformat(self.clock.now().replace("Z", "+00:00"))
        return 0 <= (now - received_at).total_seconds() <= 86400

    def pause_conversation_for_human(
        self,
        business_id: str,
        conversation_id: str,
        contact_id: str,
        *,
        reason: str = "human takeover",
    ) -> Dict[str, Any]:
        """Atomically pause automation and cancel queued commercial replies."""

        if not str(reason).strip():
            raise ValueError("reason não pode ser vazio")
        now = utc_now()
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT version, payload FROM conversations WHERE business_id = ? AND conversation_id = ?",
                (business_id, conversation_id),
            ).fetchone()
            state = self.loads(row["payload"]) if row else empty_conversation(business_id, conversation_id, contact_id)
            state["responsible"] = "human"
            state["status"] = "human_paused"
            state["phase"] = "transferido"
            state["follow_up_allowed"] = False
            state["pending"] = None
            state.setdefault("history", []).append(
                {"type": "human_takeover", "reason": str(reason)[:2000], "at": now}
            )
            state["history"] = state["history"][-40:]
            state["version"] = int(state.get("version", 0)) + 1
            if row:
                db.execute(
                    "UPDATE conversations SET version = ?, payload = ?, updated_at = ? WHERE business_id = ? AND conversation_id = ?",
                    (state["version"], self.dumps(state), now, business_id, conversation_id),
                )
            else:
                db.execute(
                    "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                    (business_id, conversation_id, state["version"], self.dumps(state), now),
                )
            db.execute(
                "UPDATE outbox SET status = 'cancelled', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'event:%' AND status = 'pending'",
                (str(reason)[:2000], now, business_id, conversation_id),
            )
            db.execute(
                "UPDATE outbox SET status = 'unknown', leased_until = NULL, lease_owner = NULL, last_error = ?, updated_at = ? "
                "WHERE business_id = ? AND conversation_id = ? AND message_key LIKE 'event:%' AND status = 'processing'",
                ("%s; delivery outcome is unknown" % str(reason)[:1900], now, business_id, conversation_id),
            )
            return state

    def mark_inbound_processed(self, message_ids: List[str], turn_id: str, *, business_id: str, conversation_id: str) -> int:
        if not message_ids:
            return 0
        placeholders = ",".join("?" for _ in message_ids)
        with self._lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE inbound_messages SET status = 'processed', turn_id = ? WHERE business_id = ? "
                "AND conversation_id = ? AND message_id IN (%s) AND status = 'queued'" % placeholders,
                (turn_id, business_id, conversation_id, *message_ids),
            )
            return cursor.rowcount

    def record_channel_event(
        self,
        channel: str,
        external_event_id: str,
        payload: Mapping[str, Any],
        *,
        status: str,
        reason: str = "",
        business_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> bool:
        """Record an authenticated channel event exactly once.

        The payload is an adapter envelope with secrets removed by the caller;
        the table is an audit ledger and is separate from buyer messages so
        private and self-authored provider events cannot enter the turn queue.
        """

        if not channel.strip() or not external_event_id.strip() or not status.strip():
            raise ValueError("evento de canal exige channel, identidade e status")
        with self._lock, self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO channel_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        channel,
                        external_event_id,
                        business_id,
                        conversation_id,
                        status,
                        reason[:500] if reason else None,
                        self.dumps(dict(payload)),
                        utc_now(),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_channel_event(self, channel: str, external_event_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM channel_events WHERE channel = ? AND external_event_id = ?",
                (channel, external_event_id),
            ).fetchone()
        if not row:
            return None
        return {
            "channel": row["channel"],
            "external_event_id": row["external_event_id"],
            "business_id": row["business_id"],
            "conversation_id": row["conversation_id"],
            "status": row["status"],
            "reason": row["reason"],
            "payload": self.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def is_admitted_channel_event(
        self,
        channel: str,
        context: Mapping[str, Any],
        *,
        business_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        contact_id: Optional[str] = None,
    ) -> bool:
        """Verify that a channel envelope was admitted by its authenticated adapter."""

        if not isinstance(context, Mapping):
            return False
        values = (context.get("account_id"), context.get("inbox_id"), context.get("external_message_id"))
        if any(value is None or not str(value).strip() for value in values):
            return False
        external_event_id = ":".join(str(value) for value in values)
        event = self.get_channel_event(channel, external_event_id)
        if not event or event.get("status") not in {"admitted", "duplicate"}:
            return False
        if business_id is not None and str(event.get("business_id")) != str(business_id):
            return False
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            return False
        if conversation_id is not None and str(payload.get("conversation_id", "")) != str(conversation_id):
            return False
        if contact_id is not None and str(payload.get("contact_id", "")) != str(contact_id):
            return False
        return True

    def save_operating_mode(
        self,
        scope_key: str,
        business_id: str,
        channel: str,
        mode: str,
        *,
        enabled: bool = True,
        cohort: Optional[Mapping[str, Any]] = None,
        limits: Optional[Mapping[str, Any]] = None,
        evaluated_package_version: Optional[str] = None,
        evaluated_package_fingerprint: Optional[str] = None,
        evaluated_model: Optional[str] = None,
        evaluated_backend: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        if mode not in {"observation", "assistance", "pilot"}:
            raise ValueError("modo operacional inválido")
        value = {
            "scope_key": scope_key,
            "business_id": business_id,
            "channel": channel,
            "mode": mode,
            "enabled": bool(enabled),
            "cohort": dict(cohort or {}),
            "limits": dict(limits or {}),
            "evaluated_package_version": evaluated_package_version,
            "evaluated_package_fingerprint": evaluated_package_fingerprint,
            "evaluated_model": evaluated_model,
            "evaluated_backend": evaluated_backend,
            "reason": reason,
            "updated_at": utc_now(),
        }
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO operating_modes(scope_key, business_id, channel, mode, enabled, cohort, limits, evaluated_package_version, evaluated_package_fingerprint, evaluated_model, evaluated_backend, reason, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(scope_key) DO UPDATE SET business_id=excluded.business_id, channel=excluded.channel, mode=excluded.mode, enabled=excluded.enabled, cohort=excluded.cohort, limits=excluded.limits, evaluated_package_version=excluded.evaluated_package_version, evaluated_package_fingerprint=excluded.evaluated_package_fingerprint, evaluated_model=excluded.evaluated_model, evaluated_backend=excluded.evaluated_backend, reason=excluded.reason, updated_at=excluded.updated_at",
                (
                    value["scope_key"],
                    value["business_id"],
                    value["channel"],
                    value["mode"],
                    1 if value["enabled"] else 0,
                    self.dumps(value["cohort"]),
                    self.dumps(value["limits"]),
                    value["evaluated_package_version"],
                    value["evaluated_package_fingerprint"],
                    value["evaluated_model"],
                    value["evaluated_backend"],
                    value["reason"],
                    value["updated_at"],
                ),
            )
        return value

    def get_operating_mode(self, scope_key: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM operating_modes WHERE scope_key = ?", (scope_key,)).fetchone()
        if not row:
            return None
        return {
            "scope_key": row["scope_key"],
            "business_id": row["business_id"],
            "channel": row["channel"],
            "mode": row["mode"],
            "enabled": bool(row["enabled"]),
            "cohort": self.loads(row["cohort"]),
            "limits": self.loads(row["limits"]),
            "evaluated_package_version": row["evaluated_package_version"],
            "evaluated_package_fingerprint": row["evaluated_package_fingerprint"],
            "evaluated_model": row["evaluated_model"],
            "evaluated_backend": row["evaluated_backend"],
            "reason": row["reason"],
            "updated_at": row["updated_at"],
        }

    def list_operating_modes(self, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as db:
            if business_id:
                rows = db.execute(
                    "SELECT scope_key FROM operating_modes WHERE business_id = ? ORDER BY scope_key", (business_id,)
                ).fetchall()
            else:
                rows = db.execute("SELECT scope_key FROM operating_modes ORDER BY scope_key").fetchall()
        return [self.get_operating_mode(str(row["scope_key"])) for row in rows]

    def update_pilot_metrics(self, scope_key: str, increments: Mapping[str, Any]) -> Dict[str, Any]:
        with self._lock, self.connect() as db:
            row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
            counters: Dict[str, Any] = self.loads(row["counters"]) if row else {}
            for key, amount in increments.items():
                if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                    continue
                value = counters.get(str(key), 0)
                counters[str(key)] = value + amount
            db.execute(
                "INSERT INTO pilot_metrics VALUES (?, ?, ?) ON CONFLICT(scope_key) DO UPDATE SET counters=excluded.counters, updated_at=excluded.updated_at",
                (scope_key, self.dumps(counters), utc_now()),
            )
            return counters

    def try_consume_pilot_limits(
        self,
        scope_key: str,
        limits: Mapping[str, Any],
        *,
        estimated_cost: float = 0.0,
        reservation_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically reserve one pilot event under its numeric limits.

        ``reservation_key`` makes the reservation durable and idempotent.  A
        delivery worker can therefore restart between admission and outcome
        recording without losing ownership of the reserved slot.
        """

        if reservation_key is not None and (not str(reservation_key).strip() or len(str(reservation_key)) > 300):
            raise ValueError("reservation_key de piloto inválida")
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = utc_now()
            if reservation_key is not None:
                existing_reservation = db.execute(
                    "SELECT estimated_cost, status FROM pilot_reservations WHERE scope_key = ? AND reservation_key = ?",
                    (scope_key, str(reservation_key)),
                ).fetchone()
                if existing_reservation:
                    row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
                    counters = self.loads(row["counters"]) if row else {}
                    status = str(existing_reservation["status"])
                    if status == "reserved":
                        return {
                            "allowed": True,
                            "reason": "pilot_slot_already_reserved",
                            "reservation_existing": True,
                            "counters": counters,
                        }
                    return {
                        "allowed": False,
                        "reason": "pilot_reservation_%s" % status,
                        "reservation_existing": True,
                        "counters": counters,
                    }
            row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
            counters: Dict[str, Any] = self.loads(row["counters"]) if row else {}
            events = float(counters.get("events", 0))
            deliveries = float(counters.get("deliveries", 0))
            cost = float(counters.get("cost", 0))
            reserved_deliveries = float(counters.get("reserved_deliveries", 0))
            reserved_cost = float(counters.get("reserved_cost", 0))
            try:
                estimated_cost = float(estimated_cost)
            except (TypeError, ValueError):
                estimated_cost = 0.0
            if not math.isfinite(estimated_cost):
                estimated_cost = 0.0
            estimated_cost = max(0.0, estimated_cost)
            checks = (
                ("max_events", events, "event_limit"),
                ("max_deliveries", deliveries + reserved_deliveries, "delivery_limit"),
                ("max_cost", cost + reserved_cost + estimated_cost, "cost_limit"),
            )
            for name, current, reason in checks:
                limit = limits.get(name)
                if limit is not None and current >= float(limit):
                    return {"allowed": False, "reason": reason, "counters": counters}
            counters["events"] = events + 1
            if counters["events"].is_integer():
                counters["events"] = int(counters["events"])
            counters["reserved_deliveries"] = reserved_deliveries + 1
            counters["reserved_cost"] = reserved_cost + estimated_cost
            if float(counters["reserved_deliveries"]).is_integer():
                counters["reserved_deliveries"] = int(counters["reserved_deliveries"])
            if float(counters["reserved_cost"]).is_integer():
                counters["reserved_cost"] = int(counters["reserved_cost"])
            db.execute(
                "INSERT INTO pilot_metrics(scope_key, counters, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(scope_key) DO UPDATE SET counters=excluded.counters, updated_at=excluded.updated_at",
                (scope_key, self.dumps(counters), now),
            )
            if reservation_key is not None:
                db.execute(
                    "INSERT INTO pilot_reservations(scope_key, reservation_key, estimated_cost, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'reserved', ?, ?)",
                    (scope_key, str(reservation_key), estimated_cost, now, now),
                )
            return {"allowed": True, "reason": "pilot_slot_reserved", "counters": counters}

    def settle_pilot_reservation(
        self,
        scope_key: str,
        reservation_key: str,
        outcome_status: str,
        *,
        actual_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Settle a durable pilot reservation exactly once.

        Unknown provider outcomes retain the reservation and are not returned
        to the send budget.  Definitive cancellation/rejection releases it;
        successful delivery converts it to a counted delivery.
        """

        if not str(reservation_key).strip():
            raise ValueError("reservation_key de piloto inválida")
        success = outcome_status in {"sent", "confirmed", "accepted"}
        unknown = outcome_status in {"unknown", "timeout"}
        release = outcome_status in {"cancelled", "observed", "dead_letter", "rejected", "pending"}
        if not (success or unknown or release):
            raise ValueError("resultado de reserva de piloto inválido: %s" % outcome_status)
        actual_cost_provided = actual_cost is not None
        try:
            actual_cost_value = max(0.0, float(actual_cost)) if actual_cost is not None else 0.0
        except (TypeError, ValueError):
            actual_cost_value = 0.0
            actual_cost_provided = False
        if not math.isfinite(actual_cost_value):
            actual_cost_value = 0.0
            actual_cost_provided = False
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reservation = db.execute(
                "SELECT estimated_cost, status FROM pilot_reservations WHERE scope_key = ? AND reservation_key = ?",
                (scope_key, str(reservation_key)),
            ).fetchone()
            if not reservation:
                row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
                counters = self.loads(row["counters"]) if row else {}
                return {"settled": False, "reason": "reservation_not_found", "counters": counters}
            current_status = str(reservation["status"])
            if current_status not in {"reserved", "unknown"}:
                row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
                return {"settled": False, "reason": "reservation_already_settled", "counters": self.loads(row["counters"]) if row else {}}
            if current_status == "unknown" and unknown:
                row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
                counters = self.loads(row["counters"]) if row else {}
                return {"settled": False, "reason": "reservation_already_unknown", "counters": counters}
            row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
            counters: Dict[str, Any] = self.loads(row["counters"]) if row else {}
            if unknown:
                new_status = "unknown"
            else:
                estimated = float(reservation["estimated_cost"])
                counters["reserved_deliveries"] = max(0.0, float(counters.get("reserved_deliveries", 0)) - 1)
                counters["reserved_cost"] = max(0.0, float(counters.get("reserved_cost", 0)) - estimated)
                if success:
                    counters["deliveries"] = float(counters.get("deliveries", 0)) + 1
                    settled_cost = actual_cost_value if actual_cost_provided else estimated
                    if settled_cost:
                        counters["cost"] = float(counters.get("cost", 0)) + settled_cost
                    new_status = "settled"
                else:
                    new_status = "released"
                for key in ("reserved_deliveries", "reserved_cost", "deliveries", "cost"):
                    if key in counters and float(counters.get(key, 0)).is_integer():
                        counters[key] = int(counters[key])
                db.execute(
                    "INSERT INTO pilot_metrics(scope_key, counters, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(scope_key) DO UPDATE SET counters=excluded.counters, updated_at=excluded.updated_at",
                    (scope_key, self.dumps(counters), utc_now()),
                )
            db.execute(
                "UPDATE pilot_reservations SET status = ?, updated_at = ? WHERE scope_key = ? AND reservation_key = ?",
                (new_status, utc_now(), scope_key, str(reservation_key)),
            )
            return {"settled": True, "status": new_status, "counters": counters}

    def get_pilot_metrics(self, scope_key: str) -> Dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT counters FROM pilot_metrics WHERE scope_key = ?", (scope_key,)).fetchone()
        return self.loads(row["counters"]) if row else {}

    def save_supervisor_review(self, review: Mapping[str, Any]) -> Dict[str, Any]:
        required = ("review_id", "candidate_id", "business_id", "conversation_id", "event_id", "mode", "status")
        if any(not str(review.get(key, "")).strip() for key in required):
            raise ValueError("revisão de supervisor incompleta")
        value = dict(review)
        value.setdefault("created_at", utc_now())
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO supervisor_reviews(review_id, candidate_id, business_id, conversation_id, event_id, package_version, state_version, mode, status, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    value["review_id"],
                    value["candidate_id"],
                    value["business_id"],
                    value["conversation_id"],
                    value["event_id"],
                    value.get("package_version"),
                    value.get("state_version"),
                    value["mode"],
                    value["status"],
                    self.dumps(value),
                    value["created_at"],
                ),
            )
        return value

    def save_supervisor_setting(
        self,
        scope_key: str,
        mode: str,
        *,
        policy: str = "optional",
        correction_limit: int = 1,
    ) -> Dict[str, Any]:
        if not scope_key.strip() or mode not in {"off", "observation", "selective"}:
            raise ValueError("configuração de supervisor inválida")
        if policy not in {"optional", "mandatory"}:
            raise ValueError("política de supervisor inválida")
        if isinstance(correction_limit, bool) or not isinstance(correction_limit, int) or correction_limit != 1:
            raise ValueError("o limite do supervisor deve ser exatamente uma correção")
        value = {
            "scope_key": scope_key,
            "mode": mode,
            "policy": policy,
            "correction_limit": correction_limit,
            "updated_at": utc_now(),
        }
        with self._lock, self.connect() as db:
            db.execute(
                "INSERT INTO supervisor_settings VALUES (?, ?, ?, ?, ?) ON CONFLICT(scope_key) DO UPDATE SET mode=excluded.mode, policy=excluded.policy, correction_limit=excluded.correction_limit, updated_at=excluded.updated_at",
                (scope_key, mode, policy, correction_limit, value["updated_at"]),
            )
        return value

    def get_supervisor_setting(self, scope_key: str = "global") -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM supervisor_settings WHERE scope_key = ?", (scope_key,)).fetchone()
        if not row:
            return None
        return {
            "scope_key": row["scope_key"],
            "mode": row["mode"],
            "policy": row["policy"],
            "correction_limit": int(row["correction_limit"]),
            "updated_at": row["updated_at"],
        }

    def list_supervisor_reviews(self, candidate_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as db:
            if candidate_id:
                rows = db.execute(
                    "SELECT payload FROM supervisor_reviews WHERE candidate_id = ? ORDER BY created_at", (candidate_id,)
                ).fetchall()
            else:
                rows = db.execute("SELECT payload FROM supervisor_reviews ORDER BY created_at").fetchall()
        return [self.loads(row["payload"]) for row in rows]
