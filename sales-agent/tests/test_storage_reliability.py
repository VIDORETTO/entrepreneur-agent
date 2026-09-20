import sqlite3
from pathlib import Path

import pytest

from sales_agent.config import seed_examples
from sales_agent.storage import DATABASE_SCHEMA_VERSION, StateStore


def test_legacy_database_is_migrated_without_losing_outbox(tmp_path: Path):
    data_dir = tmp_path / "legacy"
    data_dir.mkdir()
    database = data_dir / "state.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE outbox (message_key TEXT PRIMARY KEY, business_id TEXT NOT NULL, "
            "conversation_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO outbox VALUES ('legacy-1', 'business', 'conversation', '{}', 'pending', '2026-01-01T00:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO outbox VALUES ('legacy-processing', 'business', 'conversation', '{}', 'processing', "
            "'2026-01-01T00:00:00+00:00')"
        )

    store = StateStore(data_dir)

    assert store.schema_version() == DATABASE_SCHEMA_VERSION
    migrated = store.list_outbox()
    by_key = {item["message_key"]: item for item in migrated}
    assert by_key["legacy-1"]["attempts"] == 0
    assert by_key["legacy-1"]["available_at"] == "2026-01-01T00:00:00+00:00"
    assert by_key["legacy-processing"]["status"] == "unknown"
    assert by_key["legacy-processing"]["last_error"] == "processing lease missing; delivery outcome is unknown"


def test_event_state_and_outbox_commit_as_one_unit(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    state = store.load_conversation("azul-b2c", "atomic", "verified:test")
    state["version"] = 1
    state["summary"] = "committed atomically"
    event = {
        "business_id": "azul-b2c",
        "conversation_id": "atomic",
        "contact_id": "verified:test",
        "event_id": "event-1",
        "text": "Mensagem fictícia",
    }
    result = {"response": "Resposta fictícia", "state": state}

    status, replay = store.commit_event(
        state,
        0,
        event,
        result,
        "azul-b2c:event-1",
        {"event_id": "event-1", "response": "Resposta fictícia", "action": None},
    )

    assert status == "committed" and replay is None
    assert store.load_conversation("azul-b2c", "atomic", "verified:test")["summary"] == "committed atomically"
    assert store.get_event("azul-b2c", "atomic", "event-1")["response"] == "Resposta fictícia"
    assert store.list_outbox()[0]["message_key"] == "azul-b2c:event-1"
    duplicate, replay = store.commit_event(
        state,
        0,
        event,
        result,
        "azul-b2c:event-1",
        {"event_id": "event-1"},
    )
    assert duplicate == "duplicate"
    assert replay["response"] == "Resposta fictícia"


def test_stale_atomic_commit_changes_nothing(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    state = store.load_conversation("azul-b2c", "stale", "verified:test")
    state["version"] = 1
    store.save_conversation(state)
    stale = dict(state)
    stale["version"] = 2
    stale["summary"] = "must not persist"
    event = {
        "business_id": "azul-b2c",
        "conversation_id": "stale",
        "contact_id": "verified:test",
        "event_id": "stale-event",
        "text": "Mensagem obsoleta",
    }

    status, _ = store.commit_event(stale, 0, event, {"response": "stale"}, "stale-message", {})

    assert status == "stale"
    assert store.get_event("azul-b2c", "stale", "stale-event") is None
    assert not [item for item in store.list_outbox() if item["message_key"] == "stale-message"]
    assert store.load_conversation("azul-b2c", "stale", "verified:test")["summary"] == ""


def test_duplicate_event_with_pending_action_is_repaired_after_effect_confirmation(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    state = store.load_conversation("azul-b2c", "pending-action", "verified:test")
    effect_key = "checkout:pending-action"
    state["version"] = 1
    state["operation"] = {"type": "checkout", "status": "pending", "effect_key": effect_key}
    state["pending"] = {"type": "effect_in_progress", "effect_key": effect_key}
    state["history"] = [{"event_id": "same", "response": "aguarde", "action": {"type": "prepare_checkout", "effect_key": effect_key, "status": "pending"}}]
    event = {
        "business_id": "azul-b2c",
        "conversation_id": "pending-action",
        "contact_id": "verified:test",
        "event_id": "same",
        "text": "Quero comprar a camiseta azul",
    }
    pending_result = {
        "response": "aguarde",
        "action": {"type": "prepare_checkout", "effect_key": effect_key, "status": "pending"},
        "state": state,
        "trace": [{"type": "checkout_in_progress"}],
    }
    status, _ = store.commit_event(
        state,
        0,
        event,
        pending_result,
        "event:pending-action",
        {"event_id": "same", "response": "aguarde", "action": pending_result["action"], "defer_delivery": True},
    )
    assert status == "committed"

    created, _ = store.reserve_effect(
        effect_key,
        "checkout",
        {"business_id": "azul-b2c", "conversation_id": "pending-action", "quote_id": "quote-1"},
    )
    assert created is True
    store.update_effect(
        effect_key,
        "confirmed",
        {
            "status": "prepared",
            "checkout_id": "co-1",
            "url": "https://checkout.invalid/co-1",
            "charged": False,
        },
    )
    confirmed_action = {"type": "prepare_checkout", "effect_key": effect_key}
    confirmed_result = {
        "response": "Checkout preparado",
        "action": confirmed_action,
        "state": state,
        "trace": [],
    }
    duplicate, replay = store.commit_event(
        state,
        0,
        event,
        confirmed_result,
        "event:pending-action",
        {"event_id": "same", "response": "Checkout preparado", "action": confirmed_action},
    )

    assert duplicate == "duplicate"
    assert replay["action"]["checkout_id"] == "co-1"
    assert store.load_conversation("azul-b2c", "pending-action", "verified:test")["operation"]["status"] == "confirmed"
    assert store.list_outbox("pending")[0]["action"]["checkout_id"] == "co-1"


def test_outbox_lease_ack_retry_dead_letter_and_recovery(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    assert store.enqueue_message("message-1", "business", "conversation", {"response": "fictícia"})
    claimed = store.claim_outbox(limit=1, lease_seconds=60)
    assert claimed[0]["status"] == "processing"
    assert claimed[0]["attempts"] == 1
    assert store.ack_outbox("message-1") is True
    assert store.list_outbox("sent")[0]["message_key"] == "message-1"

    assert store.enqueue_message("message-2", "business", "conversation", {"response": "fictícia"})
    store.claim_outbox(limit=1, lease_seconds=60)
    assert store.nack_outbox("message-2", "falha simulada", max_attempts=2, delay_seconds=0) == "pending"
    store.claim_outbox(limit=1, lease_seconds=60)
    assert store.nack_outbox("message-2", "falha repetida", max_attempts=2, delay_seconds=0) == "dead_letter"
    dead = store.list_outbox("dead_letter")[0]
    assert dead["attempts"] == 2
    assert dead["last_error"] == "falha repetida"

    assert store.enqueue_message("message-3", "business", "conversation", {"response": "fictícia"})
    store.claim_outbox(limit=1, lease_seconds=60)
    with store.connect() as db:
        db.execute("UPDATE outbox SET leased_until = '2000-01-01T00:00:00+00:00' WHERE message_key = 'message-3'")
    assert store.recover_expired_outbox() == 1
    assert store.list_outbox("unknown")[0]["message_key"] == "message-3"
    assert not store.list_outbox("pending")


def test_outbox_payload_cannot_override_delivery_metadata(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    store.enqueue_message(
        "real-key",
        "real-business",
        "real-conversation",
        {"message_key": "forged", "status": "sent", "attempts": 999, "response": "fictícia"},
    )

    item = store.list_outbox()[0]

    assert item["message_key"] == "real-key"
    assert item["business_id"] == "real-business"
    assert item["conversation_id"] == "real-conversation"
    assert item["status"] == "pending"
    assert item["attempts"] == 0
    with pytest.raises(ValueError, match="status de outbox inválido"):
        store.list_outbox("forged")


def test_checkout_effect_and_inventory_are_atomic_and_compensated(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)

    outcome, effect = store.reserve_checkout_effect(
        "checkout:test",
        {"quote_id": "quote-test"},
        business_id="azul-b2c",
        offer_id="camiseta-azul",
        variant="M",
        quantity=1,
    )

    assert outcome == "reserved"
    assert effect["inventory_reservation"]["released"] is False
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0
    store.update_effect("checkout:test", "unknown", {"reason": "timeout simulado"})
    reconciled = store.reconcile_effect("checkout:test", "failed", {"resolution_source": "teste"})
    assert reconciled["inventory_reservation"]["released"] is True
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 1
    with pytest.raises(ValueError, match="não está pendente"):
        store.reconcile_effect("checkout:test", "failed")
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 1


def test_effect_transitions_and_inventory_quantity_are_guarded(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    created, _ = store.reserve_effect("proposal:guarded", "proposal", {"offer_id": "fictícia"})
    assert created is True
    store.update_effect("proposal:guarded", "confirmed", {"proposal_id": "pr_fictícia"})

    with pytest.raises(ValueError, match="transição de efeito inválida"):
        store.update_effect("proposal:guarded", "unknown", {})
    with pytest.raises(ValueError, match="inteiro positivo"):
        store.reserve_inventory("azul-b2c", "camiseta-azul", "M", -1)
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 1


def test_pilot_reservation_survives_restart_and_settles_once(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    scope_key = "azul-b2c:chatwoot"
    limits = {"max_deliveries": 2, "max_cost": 1.0}

    first = store.try_consume_pilot_limits(
        scope_key,
        limits,
        estimated_cost=0.125,
        reservation_key="pilot-restart-1",
    )
    assert first["allowed"] is True
    assert store.get_pilot_metrics(scope_key)["reserved_cost"] == pytest.approx(0.125)

    restarted = StateStore(tmp_path / "data")
    replay = restarted.try_consume_pilot_limits(
        scope_key,
        limits,
        estimated_cost=0.125,
        reservation_key="pilot-restart-1",
    )
    assert replay["allowed"] is True
    assert replay["reservation_existing"] is True

    unknown = restarted.settle_pilot_reservation(scope_key, "pilot-restart-1", "unknown")
    assert unknown["settled"] is True
    assert restarted.get_pilot_metrics(scope_key)["reserved_cost"] == pytest.approx(0.125)
    repeated_unknown = restarted.settle_pilot_reservation(scope_key, "pilot-restart-1", "unknown")
    assert repeated_unknown["settled"] is False
    assert repeated_unknown["reason"] == "reservation_already_unknown"

    settled = restarted.settle_pilot_reservation(
        scope_key,
        "pilot-restart-1",
        "sent",
        actual_cost=0.375,
    )
    assert settled["settled"] is True
    metrics = restarted.get_pilot_metrics(scope_key)
    assert metrics["reserved_cost"] == 0
    assert metrics["reserved_deliveries"] == 0
    assert metrics["deliveries"] == 1
    assert metrics["cost"] == pytest.approx(0.375)

    repeated_settlement = restarted.settle_pilot_reservation(
        scope_key,
        "pilot-restart-1",
        "sent",
        actual_cost=0.375,
    )
    assert repeated_settlement["settled"] is False
    assert repeated_settlement["reason"] == "reservation_already_settled"
    assert restarted.get_pilot_metrics(scope_key)["cost"] == pytest.approx(0.375)


def test_reconciliation_cannot_redirect_effect_or_inventory(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    store.reserve_checkout_effect(
        "checkout:protected",
        {"business_id": "azul-b2c", "conversation_id": "protected", "quote_id": "quote-protected"},
        business_id="azul-b2c",
        offer_id="camiseta-azul",
        variant="M",
        quantity=1,
    )
    store.update_effect("checkout:protected", "unknown", {"reason": "timeout simulado"})

    with pytest.raises(ValueError, match="metadado protegido"):
        store.reconcile_effect(
            "checkout:protected",
            "failed",
            {"inventory_reservation": {"business_id": "outro", "offer_id": "outro", "variant": "X", "quantity": 99}},
        )

    assert store.get_effect("checkout:protected")["status"] == "unknown"
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0


def test_backup_integrity_and_restore_preserve_a_safety_copy(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    original = store.backup_to(tmp_path / "original.sqlite3")
    state = store.load_conversation("azul-b2c", "after-backup", "verified:test")
    state["summary"] = "created after backup"
    store.save_conversation(state)

    restored = store.restore_from(original, tmp_path / "before-restore.sqlite3")

    assert Path(restored["previous_backup"]).is_file()
    assert restored["integrity"]["ok"] is True
    assert store.load_conversation("azul-b2c", "after-backup", "verified:test")["summary"] == ""
    safety = StateStore(tmp_path / "safety-check")
    with sqlite3.connect(tmp_path / "before-restore.sqlite3") as source, safety.connect() as target:
        source.backup(target)
    assert safety.load_conversation("azul-b2c", "after-backup", "verified:test")["summary"] == "created after backup"


def test_restore_rejects_corrupt_input_before_touching_active_database(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_text("not a database", encoding="utf-8")

    with pytest.raises(ValueError, match="SQLite inválido"):
        store.restore_from(corrupt, tmp_path / "safety.sqlite3")

    assert store.integrity_report()["ok"] is True
    assert not (tmp_path / "safety.sqlite3").exists()
