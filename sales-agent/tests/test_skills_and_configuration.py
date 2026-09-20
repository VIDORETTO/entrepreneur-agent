from tests.conftest import event


def test_installed_skill_catalog_exposes_only_product_audiences_and_resolves_references():
    from sales_agent.skills import SkillCatalog

    catalog = SkillCatalog()
    skills = catalog.list_skills()
    assert skills
    assert {item["audience"] for item in skills} <= {"buyer-attention", "business-configuration"}
    assert all(item["version"] for item in skills)
    assert all(not any(term in item["id"] for term in ("program", "refactor", "maintain")) for item in skills)

    configuration = catalog.read_skill("sales-business-discovery")
    assert configuration["available"] is True
    assert configuration["content"]
    assert configuration["references"]


def test_runtime_trace_distinguishes_declared_selected_and_applied_buyer_skill(app):
    store, engine = app
    package = store.get_business("azul-b2c")
    package["skills"] = [{"id": "seller-conversation", "when": "always"}]
    store.save_business(package)

    result = engine.handle(event("azul-b2c", "skill-trace", "e1", "Quanto custa a camiseta azul?"))
    trace = next(item for item in result.trace if item["type"] == "skills_selected")
    assert trace["declared"] == ["seller-conversation"]
    assert trace["selected"][0]["id"] == "seller-conversation"
    assert trace["applied"][0]["version"]
    assert trace["available"][0]["id"] == "seller-conversation"
    assert trace["sent_to_model"][0]["id"] == "seller-conversation"
    assert trace["model_observed_applied"] is None


def test_skill_selection_honors_declared_version_and_total_context_budget():
    from sales_agent.skills import SkillCatalog

    catalog = SkillCatalog()
    selected = catalog.select(
        {
            "settings": {"skill_context_budget": 40},
            "skills": [{"id": "seller-conversation", "version": "1", "when": "always"}],
        },
        "Quanto custa a oferta?",
        {},
    )

    assert selected["budget"] == {"limit": 40, "used": 40}
    assert selected["selected"][0]["version"] == "1"
    assert selected["applied"][0]["context_chars"] == 40
    context = catalog.context(selected)
    assert sum(len(item["content"]) for item in context) <= 40

    incompatible = catalog.select(
        {
            "skills": [{"id": "seller-conversation", "version": "999", "when": "always"}],
        },
        "Quanto custa a oferta?",
        {},
    )
    assert incompatible["selected"] == []
    assert incompatible["applied"] == []
    assert incompatible["unavailable"] == [{"id": "seller-conversation", "reason": "version_mismatch"}]


def test_package_validates_skill_budget_and_declared_metadata():
    from sales_agent.config import example_package
    from sales_agent.validation import PackageError, validate_package

    package = example_package("physical")
    package["settings"]["skill_context_budget"] = 0
    try:
        validate_package(package)
    except PackageError as exc:
        assert "skill_context_budget" in str(exc)
    else:
        raise AssertionError("orçamento inválido deveria impedir o pacote")

    package = example_package("physical")
    package["skills"].append({"id": "seller-conversation", "version": "1", "context_chars": 9_000})
    try:
        validate_package(package)
    except PackageError as exc:
        assert "context_chars" in str(exc)
    else:
        raise AssertionError("skill maior que o orçamento deveria impedir o pacote")

    package = example_package("physical")
    package["skills"] = [{"id": "sales-business-discovery", "version": "1", "when": "always"}]
    try:
        validate_package(package)
    except PackageError as exc:
        assert "compatível" in str(exc)
    else:
        raise AssertionError("skill de configuração não deveria entrar no runtime comprador")


def test_configuration_prioritizes_the_selected_capability_blocker(tmp_path):
    from sales_agent.config import ConfigurationManager
    from sales_agent.storage import StateStore

    manager = ConfigurationManager(StateStore(tmp_path / "data"))
    started = manager.start("handoff-config", template="service", capability="human_transfer")

    assert started["capability"] == "human_transfer"
    assert started["questions"][0]["id"] == "autonomy"
    assert started["checkpoint"]["next_blocker"] == "autonomy"


def test_conversation_memory_records_facts_and_explicit_corrections(app):
    store, engine = app
    first = engine.handle(event("azul-b2c", "memory", "e1", "Quero a camiseta azul, uma unidade para SP."))
    second = engine.handle(event("azul-b2c", "memory", "e2", "Na verdade tamanho G."))

    assert first.state["pending"]["field"] == "variant"
    assert second.state["facts"]["variant"] == "G"
    changes = second.state["memory"]["fact_history"]
    assert any(item["field"] == "variant" and item["old"] is None and item["new"] == "G" for item in changes)
    assert "variant" in second.state["memory"]["answered_fields"]


def test_configuration_inspect_diff_and_simulate_keep_active_package_isolated(app):
    from sales_agent.config import ConfigurationManager

    store, _ = app
    manager = ConfigurationManager(store)
    started = manager.start("configurable", template="service")
    for answer in ("Serviço fictício", "proposta", "material aprovado", "somente preparar"):
        manager.answer(started["session_id"], answer)
    draft = manager.finalize(started["session_id"])

    inspected = manager.inspect("configurable")
    assert inspected["lifecycle"] == "draft"
    assert inspected["capabilities"]["quote"]["state"] == "pending"
    diff = manager.diff("configurable", {**draft, "package_version": "draft-next"})
    assert diff["package_version"]["changed"] is True
    simulated = manager.simulate({**draft, "package_version": "draft-next"}, "Quero contratar o serviço fictício.")
    assert simulated["isolated"] is True
    assert store.get_business("configurable")["package_version"] == draft["package_version"]


def test_configuration_keeps_confirmed_inferred_conflicting_and_absent_facts_distinct(tmp_path):
    from sales_agent.config import ConfigurationManager
    from sales_agent.storage import StateStore

    manager = ConfigurationManager(StateStore(tmp_path / "data"))
    started = manager.start(
        "fact-states",
        template="physical",
        materials=["O preço aprovado é R$ 100, mas outra tabela informa R$ 120."],
    )

    findings = started["document_findings"]
    assert any(item["term"] == "preço" and item["status"] == "conflicting" for item in findings)
    assert any(item["status"] == "absent" for item in findings)
    assert all(item["status"] in {"confirmed", "inferred", "conflicting", "absent"} for item in findings)

    after_offer = manager.answer(started["session_id"], "Oferta física fictícia")
    assert after_offer["fact_records"]["offer"]["status"] == "confirmed"
    after_defer = manager.answer(started["session_id"], "não sei")
    assert after_defer["fact_records"]["next_step"]["status"] == "absent"
