from sales_agent.conversation import SellerEngine
from sales_agent.model import UntrustedModel

from .conftest import event


def test_ready_buyer_advances_without_qualification(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "ready", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert result.action["type"] == "prepare_checkout"
    assert result.action["charged"] is False
    assert "orçamento" not in result.response.casefold()
    assert "cargo" not in result.response.casefold()


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


def test_unknown_checkout_is_not_repeated(app):
    store, engine = app
    engine.commerce.set_behavior("checkout_timeout", True)
    result = engine.handle(event("azul-b2c", "unknown", "e1", "Quero comprar a camiseta azul tamanho M, uma unidade para SP."))

    assert result.action is None
    assert result.state["operation"]["status"] == "unknown"
    assert result.state["pending"]["type"] == "reconcile_checkout"


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
    engine.schedule_follow_up("azul-b2c", "stop", "task-stop", "Ainda posso ajudar?")
    stopped = engine.handle(event("azul-b2c", "stop", "e1", "Não quero receber mais mensagens."))
    thanked = engine.handle(event("azul-b2c", "stop", "e2", "Obrigado."))

    assert stopped.state["follow_up_allowed"] is False
    assert stopped.action is None
    assert not [item for item in store.list_outbox(status="pending") if item["message_key"].startswith("followup:")]
    assert "mais alguma" not in thanked.response.casefold()


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


def test_last_stock_is_not_promised_twice(app):
    store, engine = app
    first = engine.handle(event("azul-b2c", "stock-a", "e1", "Quero a camiseta azul tamanho M, uma unidade para SP."))
    second = engine.handle(event("azul-b2c", "stock-b", "e1", "Quero a camiseta azul tamanho M, uma unidade para SP."))

    assert first.action["type"] == "prepare_checkout"
    assert second.action is None
    assert "disponível" in second.response
