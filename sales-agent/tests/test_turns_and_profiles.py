from .conftest import event


def test_turn_assembler_groups_consecutive_messages_and_preserves_order(app):
    from sales_agent.turns import TurnAssembler

    store, engine = app
    turns = TurnAssembler(store, engine, window_seconds=30, max_wait_seconds=90)
    assert turns.receive(event("azul-b2c", "turn", "m1", "Quero a camiseta azul."), received_at="2099-01-01T00:00:00+00:00")["queued"] is True
    assert turns.receive(event("azul-b2c", "turn", "m2", "Tamanho M"), received_at="2099-01-01T00:00:10+00:00")["queued"] is True
    assert turns.receive(event("azul-b2c", "turn", "m3", "uma unidade para SP"), received_at="2099-01-01T00:00:20+00:00")["queued"] is True

    results = turns.process_due(now="2099-01-01T00:00:51+00:00")
    assert len(results) == 1
    assert results[0].action and results[0].action["type"] == "prepare_checkout"
    assert results[0].state["facts"]["variant"] == "M"
    assert results[0].state["facts"]["quantity"] == 1
    assert results[0].state["facts"]["region"] == "SP"
    assert results[0].state["turn"]["message_ids"] == ["m1", "m2", "m3"]


def test_urgent_human_request_bypasses_wait_and_duplicate_message_is_ignored(app):
    from sales_agent.turns import TurnAssembler

    store, engine = app
    turns = TurnAssembler(store, engine, window_seconds=30, max_wait_seconds=90)
    result = turns.receive(event("azul-b2c", "urgent", "m1", "Quero falar com uma pessoa."), received_at="2099-01-01T00:00:00+00:00")
    duplicate = turns.receive(event("azul-b2c", "urgent", "m1", "Quero falar com uma pessoa."), received_at="2099-01-01T00:00:01+00:00")

    assert result["processed"] is True
    assert result["result"].action["type"] == "human_transfer"
    assert duplicate["duplicate"] is True
    assert turns.process_due(now="2099-01-01T00:05:00+00:00") == []


def test_complete_response_covers_known_price_and_missing_guarantee(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "multi-question", "e1", "Qual o preço da camiseta e qual é a garantia?"))

    assert "79" in result.response
    assert "garantia" in result.response.casefold()
    assert result.evidence == [] or all("garantia" in item["content"].casefold() for item in result.evidence)
    assert any(item["type"] == "evidence_missing" for item in result.trace)


def test_post_sale_intent_changes_profile_without_opening_checkout(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "profile", "e1", "Meu pedido não chegou e preciso de suporte."))

    assert result.action is None
    assert result.state["profile"] in {"support", "post_sale"}
    assert "checkout" not in result.response.casefold()
    assert any(item["type"] == "profile_transition" for item in result.trace)


def test_limited_profile_blocks_bare_commercial_update_but_allows_explicit_resume(app):
    store, engine = app
    first = engine.handle(event("azul-b2c", "profile-limit", "e1", "Meu pedido não chegou e preciso de suporte."))
    blocked = engine.handle(event("azul-b2c", "profile-limit", "e2", "Tamanho M"))

    assert first.state["profile"] == "post_sale"
    assert blocked.action is None
    assert blocked.state["pending"]["type"] == "profile_scope"
    assert any(item["type"] == "profile_limit_enforced" for item in blocked.trace)

    resumed = engine.handle(
        event(
            "azul-b2c",
            "profile-limit",
            "e3",
            "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
        )
    )
    assert resumed.action and resumed.action["type"] == "prepare_checkout"
    assert resumed.state["profile"] == "commercial"
    assert any(item["type"] == "profile_commercial_resume" for item in resumed.trace)


def test_informational_profile_does_not_turn_a_followup_update_into_checkout(app):
    store, engine = app
    preference = engine.handle(
        event("azul-b2c", "informational-limit", "e1", "Prefiro só receber informações, sem checkout.")
    )
    blocked = engine.handle(event("azul-b2c", "informational-limit", "e2", "Agora são duas unidades."))

    assert preference.state["profile"] == "informational"
    assert blocked.action is None
    assert blocked.state["pending"]["reason"] == "commercial_resume_required"


def test_objection_uses_approved_conditions_without_inventing_discount_or_urgency(app):
    store, engine = app

    result = engine.handle(event("azul-b2c", "objection", "e1", "Está caro. Tem desconto ou é urgente decidir?"))

    assert "79" in result.response
    assert "desconto" in result.response.casefold()
    assert "urgente" not in result.response.casefold()
    assert any(item["type"] == "objection_handled" for item in result.trace)
    assert any(item["type"] == "unsupported_objection_claim_blocked" for item in result.trace)


def test_objection_composes_price_response_with_requested_guarantee(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "objection-guarantee", "e1", "Está caro. Qual a garantia da camiseta?"))

    assert "79" in result.response
    assert "garantia" in result.response.casefold()
    assert result.state["pending"]["reason"] == "partial_coverage"
    assert any(item["type"] == "objection_handled" for item in result.trace)


def test_configured_preference_transitions_profile_with_observable_source(app):
    store, engine = app

    result = engine.handle(event("azul-b2c", "preference", "e1", "Prefiro só receber informações, sem checkout."))

    assert result.action is None
    assert result.state["profile"] == "informational"
    assert result.state["memory"]["preference"]["source"] == "package-policy"
    transition = next(item for item in result.trace if item["type"] == "preference_transition")
    assert transition["source"] == "package-policy"
    assert "checkout" not in result.response.casefold()
