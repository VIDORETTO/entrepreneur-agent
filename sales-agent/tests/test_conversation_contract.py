import pytest

from sales_agent.config import ConfigurationManager, seed_package
from sales_agent.conversation import ConversationError, SellerEngine
from sales_agent.model import UntrustedModel

from .conftest import event


def test_ready_buyer_advances_without_qualification(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "ready", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert result.action["type"] == "prepare_checkout"
    assert result.action["charged"] is False
    assert "orçamento" not in result.response.casefold()
    assert "cargo" not in result.response.casefold()


def test_changed_consultative_scope_prepares_a_new_idempotent_proposal(app):
    store, engine = app
    first = engine.handle(
        event("reforma-consultiva", "proposal-version", "e1", "Quero orçamento para reforma completa da cozinha em SP.")
    )
    second = engine.handle(
        event("reforma-consultiva", "proposal-version", "e2", "Quero orçamento só de revestimentos da cozinha em SP.")
    )

    assert first.action["type"] == "prepare_proposal"
    assert second.action["type"] == "prepare_proposal"
    assert first.action["effect_key"] != second.action["effect_key"]
    assert first.action["proposal_id"] != second.action["proposal_id"]


def test_only_missing_variant_is_asked_and_previous_facts_are_reused(app):
    store, engine = app
    first = engine.handle(event("azul-b2c", "variant", "e1", "Quero a camiseta azul, uma unidade para SP."))
    second = engine.handle(event("azul-b2c", "variant", "e2", "Tamanho M"))

    assert first.state["pending"]["field"] == "variant"
    assert second.action["type"] == "prepare_checkout"
    assert second.state["facts"]["quantity"] == 1
    assert second.state["facts"]["region"] == "SP"


def test_direct_price_does_not_start_discovery(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "price", "e1", "Quanto custa a camiseta azul?"))

    assert "79" in result.response
    assert result.action is None
    assert "qual é seu orçamento" not in result.response.casefold()


def test_quote_change_invalidates_previous_conditions(app):
    store, engine = app
    first = engine.handle(event("nuvem-b2b", "quote", "e1", "Quero 4 licenças do plano padrão para a empresa Nuvem Clara, compras@nuvem.test."))
    changed = engine.handle(event("nuvem-b2b", "quote", "e2", "Agora são duas licenças parceladas."))

    assert first.action["type"] == "prepare_checkout"
    assert changed.action is None
    assert changed.state["pending"]["type"] == "quote_confirmation"
    assert changed.state["quote"]["quantity"] == 2
    assert changed.state["quote"]["payment_method"] == "installments"


def test_duplicate_event_replays_once(app):
    store, engine = app
    message = event("azul-b2c", "duplicate", "same", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
    first = engine.handle(message)
    second = engine.handle(message)

    assert first.action["type"] == "prepare_checkout"
    assert second.duplicate is True
    assert len([item for item in store.list_outbox() if item["conversation_id"] == "duplicate"]) == 1


def test_same_event_id_in_different_conversations_has_distinct_delivery_keys(app):
    store, engine = app

    first = engine.handle(event("azul-b2c", "conversation-a", "shared-id", "Quanto custa a camiseta azul?"))
    second = engine.handle(event("azul-b2c", "conversation-b", "shared-id", "Quanto custa a camiseta azul?"))
    messages = [item for item in store.list_outbox() if item.get("event_id") == "shared-id"]

    assert first.duplicate is False
    assert second.duplicate is False
    assert {item["conversation_id"] for item in messages} == {"conversation-a", "conversation-b"}
    assert len({item["message_key"] for item in messages}) == 2


def test_correction_during_processing_suppresses_stale_response(app):
    store, _ = app

    def correction_hook(current_event, candidate):
        if current_event["event_id"] == "e2":
            # A different worker receives the correction before e2 can be sent.
            from sales_agent.conversation import SellerEngine

            SellerEngine(store).handle(event("azul-b2c", "race", "correction", "Na verdade G"))

    engine = SellerEngine(store, before_send=correction_hook)
    engine.handle(event("azul-b2c", "race", "e1", "Quero a camiseta azul."))
    result = engine.handle(event("azul-b2c", "race", "e2", "Tamanho M"))
    state = store.load_conversation("azul-b2c", "race", "verified:test")

    assert result.response == ""
    assert result.action is None
    assert any(item["type"] == "stale_response_suppressed" for item in result.trace)
    assert state["facts"]["variant"] == "G"


def test_correction_after_effect_enters_reconciliation(app):
    store, _ = app

    def correction_hook(current_event, candidate):
        if current_event["event_id"] == "e2":
            SellerEngine(store).handle(event("azul-b2c", "post-effect", "correction", "Na verdade G"))

    engine = SellerEngine(store, before_send=correction_hook)
    first = engine.handle(event("azul-b2c", "post-effect", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))
    result = engine.handle(event("azul-b2c", "post-effect", "e2", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert first.action["type"] == "prepare_checkout"
    assert result.action is None
    assert result.state["pending"]["type"] == "post_effect_correction"
    assert result.state["operation"]["status"] == "unknown"
    assert "conciliação" in result.response

    reconciled = store.reconcile_effect(
        result.state["operation"]["effect_key"],
        "failed",
        {"cancelled": True, "resolution_source": "cancelamento fictício confirmado"},
    )
    resolved_state = store.load_conversation("azul-b2c", "post-effect", "verified:test")
    assert reconciled["status"] == "failed"
    assert resolved_state["operation"]["status"] == "failed"
    assert resolved_state["pending"] is None


def test_unknown_checkout_is_not_repeated(app):
    store, engine = app
    engine.commerce.set_behavior("checkout_timeout", True)
    result = engine.handle(event("azul-b2c", "unknown", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert result.action is None
    assert result.state["operation"]["status"] == "unknown"
    assert result.state["operation"]["effect_key"].startswith("checkout:")
    assert result.state["pending"]["type"] == "reconcile_checkout"

    changed = engine.handle(event("azul-b2c", "unknown", "e2", "Na verdade quero tamanho G."))

    assert changed.action is None
    assert changed.state["operation"]["effect_key"] == result.state["operation"]["effect_key"]
    assert changed.state["facts"]["variant"] == "M"
    assert any(item["type"] == "effect_reconciliation_required" for item in changed.trace)
    assert store.inventory("azul-b2c", "camiseta-azul", "G") == 3


def test_failed_checkout_reconciliation_restores_state_and_allows_new_attempt(app):
    store, engine = app
    engine.commerce.set_behavior("checkout_timeout", True)
    first = engine.handle(
        event("azul-b2c", "reconcile-failed", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
    )
    effect_key = first.state["operation"]["effect_key"]

    reconciled = store.reconcile_effect(effect_key, "failed", {"reason": "provider_declined"})
    failed_state = store.load_conversation("azul-b2c", "reconcile-failed", "verified:test")

    assert reconciled["status"] == "failed"
    assert reconciled["inventory_reservation"]["released"] is True
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 1
    assert failed_state["operation"]["status"] == "failed"
    assert failed_state["pending"] is None
    assert failed_state["quote"] is None

    engine.commerce.set_behavior("checkout_timeout", False)
    retried = engine.handle(
        event("azul-b2c", "reconcile-failed", "e2", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
    )

    assert retried.action["type"] == "prepare_checkout"
    assert retried.action["effect_key"] != effect_key
    assert retried.state["operation"]["status"] == "confirmed"
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0


def test_confirmed_checkout_reconciliation_requires_evidence_and_updates_conversation(app):
    store, engine = app
    engine.commerce.set_behavior("checkout_timeout", True)
    result = engine.handle(
        event("azul-b2c", "reconcile-confirmed", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
    )
    effect_key = result.state["operation"]["effect_key"]

    with pytest.raises(ValueError, match="checkout_id, url e charged=false"):
        store.reconcile_effect(effect_key, "confirmed", {"checkout_id": "co_incompleto"})

    reconciled = store.reconcile_effect(
        effect_key,
        "confirmed",
        {"checkout_id": "co_confirmado", "url": "https://checkout.invalid/co_confirmado", "charged": False},
    )
    state = store.load_conversation("azul-b2c", "reconcile-confirmed", "verified:test")

    assert reconciled["status"] == "confirmed"
    assert state["operation"]["status"] == "confirmed"
    assert state["operation"]["checkout_id"] == "co_confirmado"
    assert state["pending"] is None
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0
    with pytest.raises(ValueError, match="não está pendente"):
        store.reconcile_effect(effect_key, "confirmed", {"checkout_id": "co_confirmado"})


def test_human_request_pauses_automatic_seller(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "human", "e1", "Quero falar com uma pessoa."))
    later = engine.handle(event("azul-b2c", "human", "e2", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert result.state["responsible"] == "human"
    assert result.action["type"] == "human_transfer"
    assert later.action is None
    assert later.state["status"] == "human_paused"


def test_refusal_cancels_follow_up_and_does_not_restart_sale(app):
    store, engine = app
    scheduled = engine.schedule_follow_up("azul-b2c", "stop", "task-stop", "Ainda posso ajudar?")
    stopped = engine.handle(event("azul-b2c", "stop", "e1", "Não quero receber mais mensagens."))
    thanked = engine.handle(event("azul-b2c", "stop", "e2", "Obrigado."))

    assert stopped.state["follow_up_allowed"] is False
    assert scheduled["scheduled"] is False
    assert scheduled["reason"] == "capability disabled"
    assert stopped.action is None
    assert not [item for item in store.list_outbox(status="pending") if item["message_key"].startswith("followup:")]
    assert "mais alguma" not in thanked.response.casefold()


def test_followup_keys_and_cancellation_are_scoped_to_conversation(app):
    store, engine = app
    package = store.get_business("azul-b2c")
    package["capabilities"]["follow_up"] = {"state": "enabled", "reason": "teste fictício"}
    store.save_business(package)

    assert engine.schedule_follow_up("azul-b2c", "followup-a", "same-task", "Mensagem A")["scheduled"] is True
    assert engine.schedule_follow_up("azul-b2c", "followup-b", "same-task", "Mensagem B")["scheduled"] is True
    state = store.load_conversation("azul-b2c", "followup-a", "verified:test")
    state["follow_up_allowed"] = False
    store.save_conversation(state)

    assert engine.revalidate_follow_up("azul-b2c", "followup-a", "same-task")["send"] is False
    items = {item["conversation_id"]: item for item in store.list_outbox() if item["message_key"].startswith("followup:")}
    assert items["followup-a"]["status"] == "cancelled"
    assert items["followup-b"]["status"] == "pending"


def test_payment_proof_is_not_provider_confirmation(app):
    store, engine = app
    result = engine.handle(event("curso-digital", "proof", "e1", "Enviei o comprovante do Pix."))

    assert result.action is None
    assert result.state["operation"]["payment_status"] == "pending"
    assert "confirmado" in result.response.casefold()


def test_untrusted_model_cannot_charge_or_fabricate_effect(app):
    store, _ = app
    state = store.load_conversation("azul-b2c", "unsafe", "verified:test")
    state["facts"] = {"offer_id": "camiseta-azul", "variant": "M", "quantity": 1, "region": "SP"}
    store.save_conversation(state)
    engine = SellerEngine(store, model=UntrustedModel())
    result = engine.handle(event("azul-b2c", "unsafe", "e1", "pode cobrar"))

    assert result.action is None
    assert result.state["pending"]["type"] == "unsafe_model_action"
    assert not [item for item in store.list_outbox() if (item.get("action") or {}).get("type") == "charge"]


def test_untrusted_model_facts_are_type_checked_before_business_logic(app):
    store, _ = app

    class InvalidFactsModel:
        name = "invalid-facts"

        def propose(self, text, package, state):
            from sales_agent.types import Proposal

            return Proposal(
                intent="buy",
                offer_id="camiseta-azul",
                facts={"quantity": {"forged": 1}, "variant": ["M"], "delivery": {"status": "confirmed"}},
                model_name=self.name,
            )

    result = SellerEngine(store, model=InvalidFactsModel()).handle(
        event("azul-b2c", "invalid-facts", "e1", "mensagem fictícia")
    )

    assert result.action is None
    assert result.state["pending"]["field"] == "variant"
    assert "delivery" not in result.state["facts"]
    assert len([item for item in result.trace if item["type"] == "fact_rejected"]) == 3


def test_last_stock_is_not_promised_twice(app):
    store, engine = app
    first = engine.handle(event("azul-b2c", "stock-a", "e1", "Quero a camiseta azul tamanho M, uma unidade para SP."))
    second = engine.handle(event("azul-b2c", "stock-b", "e1", "Quero a camiseta azul tamanho M, uma unidade para SP."))

    assert first.action["type"] == "prepare_checkout"
    assert second.action is None
    assert "disponível" in second.response


def test_configuration_draft_cannot_prepare_unapproved_proposal(app):
    store, _ = app
    manager = ConfigurationManager(store)
    started = manager.start("draft-business", template="service")
    for answer in ("Reforma fictícia", "proposta", "ainda sem catálogo", "somente preparar"):
        manager.answer(started["session_id"], answer)
    package = manager.finalize(started["session_id"])
    state = store.load_conversation("draft-business", "draft-conversation", "verified:test")
    state["facts"] = {"offer_id": package["offers"][0]["id"], "scope": "reforma completa"}
    store.save_conversation(state)

    result = SellerEngine(store).handle(
        event("draft-business", "draft-conversation", "e1", "Quero comprar a reforma fictícia.")
    )

    assert result.action is None
    assert result.state["pending"]["type"] == "quote_disabled"
    assert any(item.get("type") == "capability_blocked" for item in result.trace)


def test_disabled_capabilities_block_catalog_knowledge_and_transfer(app):
    store, _ = app
    package = store.get_business("curso-digital")
    for name in ("catalog_query", "knowledge_query", "human_transfer"):
        package["capabilities"][name] = {"state": "disabled", "reason": "teste sem integração"}
    seed_package(store, package)
    engine = SellerEngine(store)

    price = engine.handle(event("curso-digital", "caps-price", "e1", "Quanto custa o curso?"))
    knowledge = engine.handle(event("curso-digital", "caps-knowledge", "e1", "Como funciona o acesso?"))
    human = engine.handle(event("curso-digital", "caps-human", "e1", "Quero falar com uma pessoa."))

    assert price.action is None and price.state["pending"]["type"] == "catalog_disabled"
    assert knowledge.action is None and knowledge.state["pending"]["type"] == "knowledge_disabled"
    assert human.action is None and human.state["pending"]["type"] == "human_transfer_unavailable"
    assert human.state["status"] == "human_paused"


def test_event_contract_rejects_non_text_and_oversized_input(app):
    _, engine = app
    malformed = event("azul-b2c", "invalid", "e1", "Olá")
    malformed["text"] = {"prompt": "not text"}
    with pytest.raises(ConversationError, match="campo obrigatório"):
        engine.handle(malformed)
    oversized = event("azul-b2c", "invalid", "e2", "x" * 20_001)
    with pytest.raises(ConversationError, match="excede"):
        engine.handle(oversized)
