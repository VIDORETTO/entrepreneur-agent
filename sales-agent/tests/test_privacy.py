"""Subject access and erasure through the public privacy service."""

from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.privacy import PrivacyManager
from sales_agent.storage import StateStore

from .conftest import event


def test_ac045_export_is_scoped_to_contact(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    engine = SellerEngine(store)
    engine.handle(event("azul-b2c", "a", "a1", "Olá, sou Ana", "contact:ana"))
    engine.handle(event("azul-b2c", "b", "b1", "Olá, sou Beto", "contact:beto"))

    result = PrivacyManager(store).export("azul-b2c", "contact:ana")
    assert len(result["conversations"]) == 1
    assert result["conversations"][0]["conversation_id"] == "a"
    assert "Beto" not in str(result)


def test_ac046_erase_removes_subject_data_and_preserves_effects_and_metrics(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    engine = SellerEngine(store)
    engine.handle(event("azul-b2c", "private-order", "e1", "Quero comprar camiseta azul tamanho M 1 unidade para SP", "verified:ana"))
    store.update_pilot_metrics("scope", {"messages": 1})
    before = store.get_pilot_metrics("scope")
    assert store.list_effects()

    result = PrivacyManager(store).erase("azul-b2c", "verified:ana")
    assert result["erased_conversations"] == 1
    assert PrivacyManager(store).export("azul-b2c", "verified:ana")["conversations"] == []
    effects = store.list_effects()
    assert effects and "private-order" not in str(effects)
    assert "pseudonym" in str(effects)
    assert store.get_pilot_metrics("scope") == before


def test_ac047_redaction_removes_literal_personal_data_from_report(tmp_path):
    from sales_agent.privacy import redact_data

    report = {"message": "Telefone +55 11 91234-5678, ana.teste@example.com, CPF 123.456.789-09",
              "nested": ["ana.teste@example.com"]}
    clean = redact_data(report)
    serialized = str(clean)
    for literal in ("+55 11 91234-5678", "ana.teste@example.com", "123.456.789-09"):
        assert literal not in serialized
    assert "[REDACTED]" in serialized


def test_ac048_purge_old_messages_keeps_pending_outbox(tmp_path):
    from datetime import datetime, timedelta, timezone

    from sales_agent.clock import FixedClock

    old = datetime.now(timezone.utc) - timedelta(days=31)
    store = StateStore(tmp_path, clock=FixedClock(old.isoformat()))
    seed_examples(store)
    SellerEngine(store).handle(event("azul-b2c", "old", "e1", "Olá antiga mensagem", "verified:old"))
    assert store.list_outbox("pending")

    result = PrivacyManager(store).purge("azul-b2c", retention_days=30)
    assert result["removed_events"] >= 1
    assert store.list_outbox("pending")
    assert "antiga mensagem" not in str(PrivacyManager(store).export("azul-b2c", "verified:old"))


def test_queued_inbound_is_exported_and_erased_before_conversation(tmp_path):
    store = StateStore(tmp_path)
    store.save_inbound_message(event("shop", "queued", "q1", "Mensagem pendente", "contact:queue"),
                               "2026-09-28T12:00:00+00:00")
    privacy = PrivacyManager(store)
    assert privacy.export("shop", "contact:queue")["messages"][0]["text"] == "Mensagem pendente"
    privacy.erase("shop", "contact:queue")
    assert privacy.export("shop", "contact:queue")["messages"] == []
