from .conftest import event


class RecordingProvider:
    def __init__(self):
        self.sent = []

    def send(self, payload, *, idempotency_key):
        self.sent.append((payload, idempotency_key))
        return {"status": "sent", "provider_id": "fake-message-1"}


def test_expired_worker_cannot_requeue_or_ack_an_unknown_delivery(app):
    store, engine = app
    engine.handle(event("azul-b2c", "lease", "e1", "Quanto custa a camiseta azul?"))

    first = store.claim_outbox(limit=1, lease_seconds=60, now="2099-09-18T12:00:00+00:00")
    assert len(first) == 1
    old_owner = first[0]["lease_owner"]

    assert store.recover_expired_outbox(now="2099-09-18T12:02:00+00:00") == 1
    second = store.claim_outbox(limit=1, lease_seconds=60, now="2099-09-18T12:02:00+00:00")
    assert second == []
    assert store.list_outbox("unknown")[0]["lease_owner"] is None
    assert store.ack_outbox(first[0]["message_key"], lease_owner=old_owner) is False


def test_expired_delivery_is_unknown_until_operator_reconciles_it(app):
    store, engine = app
    engine.handle(event("azul-b2c", "unknown-outbox", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1, lease_seconds=60, now="2099-09-18T12:00:00+00:00")[0]

    assert store.recover_expired_outbox(now="2099-09-18T12:02:00+00:00") == 1
    unknown = store.list_outbox("unknown")[0]
    assert unknown["message_key"] == claimed["message_key"]
    assert not store.claim_outbox(limit=1, now="2099-09-18T12:03:00+00:00")

    reconciled = store.reconcile_outbox(
        claimed["message_key"],
        "sent",
        {"provider": {"provider_id": "fake-message-1"}, "reason": "confirmed by local contract"},
    )
    assert reconciled["status"] == "sent"
    assert store.list_outbox("unknown") == []


def test_delivery_cycle_revalidates_human_takeover_before_provider_send(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    engine.handle(event("azul-b2c", "delivery-revalidation", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)
    assert claimed

    state = store.load_conversation("azul-b2c", "delivery-revalidation", "verified:test")
    state["responsible"] = "human"
    state["status"] = "human_paused"
    store.save_conversation(state)

    provider = RecordingProvider()
    outcome = DeliveryProcessor(store).process_claimed(provider, claimed[0])

    assert outcome["status"] == "cancelled"
    assert provider.sent == []


def test_recovered_expired_lease_is_not_sent_by_an_old_delivery_worker(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    engine.handle(event("azul-b2c", "expired-worker", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1, lease_seconds=60, now="2099-09-18T12:00:00+00:00")[0]
    assert store.recover_expired_outbox(now="2099-09-18T12:02:00+00:00") == 1

    provider = RecordingProvider()
    outcome = DeliveryProcessor(store).process_claimed(provider, claimed)

    assert outcome["status"] == "unknown"
    assert outcome["reason"] == "lease_lost_before_provider"
    assert provider.sent == []


def test_ownerless_ack_and_nack_keep_legacy_cli_compatibility(tmp_path):
    from sales_agent.storage import StateStore

    store = StateStore(tmp_path / "data")
    store.enqueue_message("ownerless-ack", "business", "conversation", {"response": "fictícia"})
    assert store.claim_outbox(limit=1)[0]["lease_owner"]
    assert store.ack_outbox("ownerless-ack") is True

    store.enqueue_message("ownerless-nack", "business", "conversation", {"response": "fictícia"})
    assert store.claim_outbox(limit=1)[0]["lease_owner"]
    assert store.nack_outbox("ownerless-nack", "falha fictícia", delay_seconds=0) == "pending"


def test_human_takeover_marks_inflight_delivery_unknown(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    engine.handle(event("azul-b2c", "delivery-inflight", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)[0]
    engine.handle(event("azul-b2c", "delivery-inflight", "e2", "Quero falar com uma pessoa."))

    outcome = DeliveryProcessor(store).process_claimed(RecordingProvider(), claimed)

    assert outcome["status"] == "unknown"
    assert store.list_outbox("unknown")


def test_source_revocation_survives_reimport_and_restart(app):
    from sales_agent.knowledge import PersistentFarolKnowledge
    from sales_agent.storage import StateStore

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest("azul-b2c", "policy", "v1", "A garantia fictícia é de 30 dias.", title="Garantia")
    assert knowledge.search("azul-b2c", "garantia", 5)

    assert knowledge.revoke("azul-b2c", "policy") == 1
    knowledge.ingest("azul-b2c", "policy", "v1", "A garantia fictícia é de 30 dias.", title="Garantia")
    restarted = PersistentFarolKnowledge(StateStore(store.data_dir))
    assert restarted.search("azul-b2c", "garantia", 5) == []


def test_source_revision_cannot_change_content_in_place(app):
    from sales_agent.knowledge import PersistentFarolKnowledge

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest("immutable-business", "policy", "v1", "A política fictícia vale 30 dias.", title="Política")

    try:
        knowledge.ingest("immutable-business", "policy", "v1", "A política fictícia vale 60 dias.", title="Política")
    except ValueError as exc:
        assert "imutável" in str(exc)
    else:
        raise AssertionError("uma revisão não deve mudar de conteúdo em lugar")


def test_knowledge_query_uses_explicitly_promoted_current_revision(app):
    from sales_agent.knowledge import PersistentFarolKnowledge

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest(
        "revision-business",
        "access-policy",
        "v1",
        "O acesso fictício dura 6 meses.",
        title="Acesso",
        subject="access",
        scope="curso-analise",
        active=True,
    )
    knowledge.ingest(
        "revision-business",
        "access-policy",
        "v2",
        "O acesso fictício dura 24 meses.",
        title="Acesso",
        subject="access",
        scope="curso-analise",
        active=False,
    )

    first = knowledge.search("revision-business", "quanto dura o acesso", 5)
    assert [item["source_version"] for item in first] == ["v1"]

    assert knowledge.promote("revision-business", "access-policy", "v2") is True
    current = knowledge.search("revision-business", "quanto dura o acesso", 5)
    assert [item["source_version"] for item in current] == ["v2"]
    assert "24 meses" in current[0]["content"]


def test_knowledge_answer_declares_missing_topic_instead_of_using_related_catalog(app):
    store, engine = app

    result = engine.handle(event("azul-b2c", "pertinence", "e1", "Qual é a garantia da camiseta azul?"))

    assert "não encontrei" in result.response.casefold() or "não há" in result.response.casefold()
    assert result.evidence == []
    assert result.state["pending"]["reason"] == "no_authorized_source"


def test_knowledge_without_a_declared_topic_fails_closed(app):
    from sales_agent.conversation import SellerEngine
    from sales_agent.types import Proposal

    store, _ = app

    class TopiclessModel:
        name = "topicless-fictional-model"

        def propose(self, text, package, state):
            return Proposal(intent="knowledge", offer_id="camiseta-azul", topics=[], model_name=self.name)

    result = SellerEngine(store, model=TopiclessModel()).handle(
        event("azul-b2c", "topicless", "e1", "Quero saber uma condição")
    )

    assert result.action is None
    assert result.evidence == []
    assert result.state["pending"]["reason"] == "no_authorized_source"
    assert any(item["type"] == "evidence_topic_missing" for item in result.trace)


def test_single_negative_guarantee_policy_is_answered_but_conflicting_policies_block(app):
    store, engine = app
    engine.knowledge.ingest(
        "azul-b2c",
        "guarantee-negative",
        "v1",
        "A garantia da camiseta não cobre danos acidentais.",
        title="Garantia da camiseta",
        scope="camiseta-azul",
        audience="buyer",
    )

    answered = engine.handle(event("azul-b2c", "guarantee-negative", "e1", "Qual é a garantia da camiseta?"))

    assert "não cobre danos acidentais" in answered.response.casefold()
    assert answered.state["pending"] is None

    engine.knowledge.ingest(
        "azul-b2c",
        "guarantee-positive",
        "v1",
        "A garantia da camiseta cobre defeitos de fabricação.",
        title="Garantia alternativa",
        scope="camiseta-azul",
        audience="buyer",
    )
    blocked = engine.handle(event("azul-b2c", "guarantee-conflict", "e1", "Qual é a garantia da camiseta?"))

    assert blocked.state["pending"]["reason"] == "material_conflict"
    assert "conflitantes" in blocked.response.casefold()


def test_return_policy_conflict_is_not_collapsed_into_guarantee_or_exchange(app):
    store, engine = app
    engine.knowledge.ingest(
        "azul-b2c",
        "return-positive",
        "v1",
        "A política de devolução aceita devolução em até 7 dias.",
        title="Devolução aprovada",
        scope="camiseta-azul",
        audience="buyer",
        subject="return",
    )
    engine.knowledge.ingest(
        "azul-b2c",
        "return-negative",
        "v1",
        "A política de devolução não aceita devolução após o recebimento.",
        title="Devolução restrita",
        scope="camiseta-azul",
        audience="buyer",
        subject="return",
    )

    result = engine.handle(event("azul-b2c", "return-conflict", "e1", "Qual é a política de devolução da camiseta?"))

    assert result.state["pending"]["reason"] == "material_conflict"
    assert result.state["pending"]["topics"] == ["return"]


def test_subject_scoping_does_not_use_exchange_source_as_guarantee_evidence(app):
    store, engine = app
    engine.knowledge.ingest(
        "azul-b2c",
        "exchange-only",
        "v1",
        "A política de troca menciona garantia apenas como referência histórica.",
        title="Troca",
        scope="camiseta-azul",
        audience="buyer",
        subject="exchange",
    )

    result = engine.handle(event("azul-b2c", "subject-scope", "e1", "Qual é a garantia da camiseta?"))

    assert result.evidence == []
    assert result.state["pending"]["reason"] == "no_authorized_source"


def test_generic_knowledge_search_keeps_policy_topics_distinct(app):
    from sales_agent.knowledge import PersistentFarolKnowledge

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest(
        "topic-search",
        "exchange-only",
        "v1",
        "A política de troca aceita troca em 30 dias.",
        title="Troca",
        subject="exchange",
    )

    assert knowledge.search("topic-search", "Qual é a garantia?", 5) == []


def test_pending_evidence_reply_is_cancelled_after_source_revocation(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    result = engine.handle(event("curso-digital", "evidence-outbox", "e1", "Como funciona o acesso ao curso?"))
    assert result.evidence
    claimed = store.claim_outbox(limit=1)
    assert claimed

    engine.knowledge.revoke("curso-digital", result.evidence[0]["source_id"], result.evidence[0]["source_version"])
    provider = RecordingProvider()
    outcome = DeliveryProcessor(store).process_claimed(provider, claimed[0])

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "evidence_invalidated"
    assert provider.sent == []


def test_delivery_revalidation_rejects_changed_evidence_metadata(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    result = engine.handle(event("curso-digital", "evidence-metadata", "e1", "Como funciona o acesso ao curso?"))
    claimed = store.claim_outbox(limit=1)[0]
    evidence = result.evidence[0]
    with store.connect() as db:
        db.execute(
            "UPDATE knowledge_sources SET audience = 'internal' WHERE business_id = ? AND source_id = ? AND source_version = ?",
            ("curso-digital", evidence["source_id"], evidence["source_version"]),
        )

    provider = RecordingProvider()
    outcome = DeliveryProcessor(store).process_claimed(provider, claimed)

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "evidence_invalidated"
    assert provider.sent == []


def test_delivery_revalidation_rejects_changed_package_state_and_capability(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    engine.handle(event("azul-b2c", "delivery-version", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)[0]
    package = store.get_business("azul-b2c")
    package["package_version"] = "2.0.0"
    store.save_business(package)
    outcome = DeliveryProcessor(store).process_claimed(RecordingProvider(), claimed)

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "package_changed"

    engine.handle(event("azul-b2c", "delivery-state", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)[0]
    state = store.load_conversation("azul-b2c", "delivery-state", "verified:test")
    state["version"] += 1
    store.save_conversation(state)
    outcome = DeliveryProcessor(store).process_claimed(RecordingProvider(), claimed)

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "state_changed"

    engine.handle(event("azul-b2c", "delivery-capability", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)[0]
    package = store.get_business("azul-b2c")
    package["capabilities"]["catalog_query"] = {"state": "disabled", "reason": "pausado para revisão"}
    store.save_business(package)
    outcome = DeliveryProcessor(store).process_claimed(RecordingProvider(), claimed)

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "capability_changed"


def test_delivery_revalidation_rejects_package_edit_with_reused_version(app):
    from sales_agent.delivery import DeliveryProcessor

    store, engine = app
    engine.handle(event("azul-b2c", "delivery-fingerprint", "e1", "Quanto custa a camiseta azul?"))
    claimed = store.claim_outbox(limit=1)[0]
    package = store.get_business("azul-b2c")
    original_version = package["package_version"]
    package["offers"][0]["price"] = 80
    assert package["package_version"] == original_version
    store.save_business(package)

    outcome = DeliveryProcessor(store).process_claimed(RecordingProvider(), claimed)

    assert outcome["status"] == "cancelled"
    assert outcome["reason"] == "package_changed"


def test_farol_import_validates_generation_before_atomic_promotion(app, tmp_path):
    from sales_agent.knowledge import FarolArtifactImporter, PersistentFarolKnowledge

    store, _ = app
    root = tmp_path / "artifact"
    documents = root / "rag" / "documents"
    documents.mkdir(parents=True)
    (documents / "valid.md").write_text("A política fictícia informa 30 dias.", encoding="utf-8")
    (documents / "missing-revision.md").write_text("Documento sem revisão.", encoding="utf-8")
    (root / "rag" / "sources.json").write_text(
        '{"schema_version": 1, "generation": "gen-1", "sources": ['
        '{"destination":"valid.md","source_id":"policy","observed_revision":"r1"}]}'
        , encoding="utf-8"
    )

    knowledge = PersistentFarolKnowledge(store)
    try:
        FarolArtifactImporter(knowledge).import_package("import-business", root)
    except ValueError as exc:
        assert "revis" in str(exc).casefold()
    else:
        raise AssertionError("artefato sem revisão deveria ser rejeitado")
    assert knowledge.search("import-business", "política", 5) == []


def test_farol_manifest_requires_content_hash_for_non_legacy_documents(app, tmp_path):
    from sales_agent.knowledge import FarolArtifactImporter, PersistentFarolKnowledge

    store, _ = app
    root = tmp_path / "hash-required-artifact"
    documents = root / "rag" / "documents"
    documents.mkdir(parents=True)
    (documents / "policy.md").write_text("A política fictícia informa 30 dias.", encoding="utf-8")
    (root / "rag" / "sources.json").write_text(
        '{"schema_version": 1, "generation": "gen-hash", "sources": ['
        '{"destination":"policy.md","source_id":"policy","observed_revision":"r1"}]}',
        encoding="utf-8",
    )

    knowledge = PersistentFarolKnowledge(store)
    try:
        FarolArtifactImporter(knowledge).import_package("hash-business", root)
    except ValueError as exc:
        assert "hash" in str(exc).casefold()
    else:
        raise AssertionError("artefato sem hash deveria ser rejeitado")
    assert knowledge.search("hash-business", "política", 5) == []


def test_reapproval_is_scoped_audited_and_cannot_override_upstream_revocation(app):
    from sales_agent.knowledge import PersistentFarolKnowledge

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest("audit-business", "policy", "v1", "Garantia fictícia de 30 dias", title="Garantia")
    knowledge.revoke("audit-business", "policy", "v1")
    assert knowledge.search("audit-business", "garantia", 5) == []

    assert knowledge.reapprove("audit-business", "policy", "v1", "revisão do dono") is True
    assert knowledge.search("audit-business", "garantia", 5)
    events = store.list_governance_events("audit-business")
    assert events[-1]["action"] == "reapprove"
    assert events[-1]["source_version"] == "v1"

    store.put_sources_atomic(
        [{
            "business_id": "audit-business",
            "source_id": "policy",
            "source_version": "v2",
            "title": "Garantia",
            "content": "Garantia fictícia de 60 dias",
            "locator": "policy-v2.md",
            "origin": "farol-artifact",
            "status": "approved",
            "content_hash": __import__("hashlib").sha256("Garantia fictícia de 60 dias".encode()).hexdigest(),
            "backend": "farol-artifact-v1",
            "active": True,
        }],
        generation="gen-2",
        revocations=[{"business_id": "audit-business", "source_id": "policy", "source_version": "v2"}],
    )
    try:
        knowledge.reapprove("audit-business", "policy", "v2", "não superar bloqueio upstream")
    except ValueError as exc:
        assert "upstream" in str(exc)
    else:
        raise AssertionError("reaprovação local não deve superar revogação upstream")


def test_knowledge_search_excludes_internal_sources_and_keeps_revision_selection_explicit(app):
    from sales_agent.knowledge import PersistentFarolKnowledge

    store, _ = app
    knowledge = PersistentFarolKnowledge(store)
    knowledge.ingest(
        "scope-business",
        "public",
        "v1",
        "A entrega pública leva 3 dias",
        title="Entrega",
        audience="buyer",
        scope="offer",
        subject="delivery",
    )
    knowledge.ingest(
        "scope-business",
        "public",
        "v2",
        "A entrega pública leva 7 dias",
        title="Entrega",
        audience="buyer",
        scope="offer",
        subject="delivery",
    )
    knowledge.ingest("scope-business", "internal", "v1", "A entrega interna leva 99 dias", title="Interno", audience="internal", scope="offer", subject="delivery", active=True)

    hits = knowledge.search("scope-business", "qual o prazo de entrega", 5, audience="buyer", scope="offer")
    assert all("99 dias" not in item["content"] for item in hits)
    assert [item["source_version"] for item in hits] == ["v1"]
    assert knowledge.promote("scope-business", "public", "v2") is True
    assert [item["source_version"] for item in knowledge.search("scope-business", "qual o prazo de entrega", 5, audience="buyer", scope="offer")] == ["v2"]
