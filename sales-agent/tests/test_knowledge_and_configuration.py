import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from sales_agent.config import ConfigurationManager, example_package, promote_package, seed_examples, seed_package
from sales_agent.knowledge import FarolArtifactImporter, PersistentFarolKnowledge
from sales_agent.storage import StateStore
from sales_agent.validation import PackageError, validate_package


def test_persistent_evidence_has_origin_version_and_business_isolation(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    backend = PersistentFarolKnowledge(store)

    hits = backend.search("azul-b2c", "quanto custa a camiseta", 5)
    assert hits[0]["content"]
    assert hits[0]["source_version"] == "2026-09-17.1"
    assert hits[0]["backend"] == "sqlite-farol-v1"
    assert backend.search("curso-digital", "camiseta", 5) == []

    assert backend.revoke("azul-b2c", "azul-catalogo", "2026-09-17.1") == 1
    assert backend.search("azul-b2c", "quanto custa a camiseta", 5) == []


def test_package_source_snapshot_deactivates_removed_history(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    package = example_package("physical", business_id="snapshot-business")
    seed_package(store, package)
    backend = PersistentFarolKnowledge(store)
    assert backend.search("snapshot-business", "quanto custa camiseta", 5)

    replacement = deepcopy(package)
    replacement["package_version"] = "1.0.1"
    replacement["sources"] = []
    seed_package(store, replacement)

    assert backend.search("snapshot-business", "quanto custa camiseta", 5) == []
    history = backend.list_sources("snapshot-business")
    assert history and history[0]["active"] is False


def test_farol_artifact_import_uses_persistent_adapter(tmp_path: Path):
    artifact = tmp_path / "farol-package"
    (artifact / "rag" / "documents").mkdir(parents=True)
    (artifact / "rag" / "documents" / "guide.md").write_text("O acesso dura 30 dias.", encoding="utf-8")
    store = StateStore(tmp_path / "data")
    backend = PersistentFarolKnowledge(store)

    count = FarolArtifactImporter(backend).import_package("artifact-business", artifact)
    sources = backend.list_sources("artifact-business")
    assert sources[0]["review_status"] == "pending_review"
    assert backend.promote(
        "artifact-business", sources[0]["source_id"], sources[0]["source_version"]
    ) is False
    assert backend.search("artifact-business", "acesso dura", 5) == []
    assert backend.review_legacy(
        "artifact-business",
        sources[0]["source_id"],
        sources[0]["source_version"],
        "revisão fictícia do operador",
    ) is True
    hits = backend.search("artifact-business", "acesso dura", 5)

    assert count == 1
    assert hits[0]["backend"] == "farol-artifact-v1"
    assert hits[0]["locator"] == "guide.md"


def test_farol_artifact_rejects_symlinked_rag_root(tmp_path: Path):
    artifact = tmp_path / "symlinked-rag"
    outside = tmp_path / "outside-rag"
    (outside / "documents").mkdir(parents=True)
    (outside / "documents" / "guide.md").write_text("Conteúdo fictício externo.", encoding="utf-8")
    artifact.mkdir()
    try:
        os.symlink(outside, artifact / "rag", target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlink não disponível neste ambiente")

    backend = PersistentFarolKnowledge(StateStore(tmp_path / "data"))
    with pytest.raises(ValueError, match="rag"):
        FarolArtifactImporter(backend).import_package("symlink-business", artifact)
    assert backend.list_sources("symlink-business") == []


def test_farol_import_rejects_two_active_revisions_in_one_scope(tmp_path: Path):
    import hashlib

    artifact = tmp_path / "duplicate-active"
    documents = artifact / "rag" / "documents"
    documents.mkdir(parents=True)
    entries = []
    for filename, revision, content in (
        ("first.md", "r1", "A entrega fictícia leva 3 dias."),
        ("second.md", "r2", "A entrega fictícia leva 7 dias."),
    ):
        (documents / filename).write_text(content, encoding="utf-8")
        entries.append(
            {
                "destination": filename,
                "source_id": "delivery",
                "observed_revision": revision,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "status": "approved",
                "active": True,
                "scope": "offer",
                "audience": "buyer",
                "subject": "delivery",
            }
        )
    (artifact / "rag" / "sources.json").write_text(
        json.dumps({"schema_version": 1, "generation": "duplicate-generation", "sources": entries}),
        encoding="utf-8",
    )

    backend = PersistentFarolKnowledge(StateStore(tmp_path / "data"))
    with pytest.raises(ValueError, match="mais de uma revisão ativa"):
        FarolArtifactImporter(backend).import_package("duplicate-business", artifact)
    assert backend.list_sources("duplicate-business") == []


def test_farol_import_rejects_reversed_validity_interval(tmp_path: Path):
    import hashlib

    artifact = tmp_path / "invalid-validity"
    documents = artifact / "rag" / "documents"
    documents.mkdir(parents=True)
    content = "A condição fictícia está documentada."
    (documents / "policy.md").write_text(content, encoding="utf-8")
    (artifact / "rag" / "sources.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generation": "invalid-validity-generation",
                "sources": [
                    {
                        "destination": "policy.md",
                        "source_id": "policy",
                        "observed_revision": "r1",
                        "sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "status": "approved",
                        "active": True,
                        "valid_from": "2026-09-21T00:00:00Z",
                        "valid_until": "2026-09-20T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    backend = PersistentFarolKnowledge(StateStore(tmp_path / "data"))
    with pytest.raises(ValueError, match="vigência inválida"):
        FarolArtifactImporter(backend).import_package("invalid-validity-business", artifact)


def test_farol_manifest_normalizes_offset_dates_and_replaces_previous_generation(tmp_path: Path):
    import hashlib

    def make_artifact(root: Path, generation: str, filename: str, content: str, valid_from: str, valid_until: str):
        documents = root / "rag" / "documents"
        documents.mkdir(parents=True)
        (documents / filename).write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode()).hexdigest()
        (root / "rag" / "sources.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "generation": generation,
                    "sources": [
                        {
                            "destination": filename,
                            "source_id": "policy",
                            "observed_revision": generation,
                            "sha256": digest,
                            "status": "approved",
                            "active": True,
                            "audience": "buyer",
                            "valid_from": valid_from,
                            "valid_until": valid_until,
                        }
                    ],
                    "revocations": [],
                }
            ),
            encoding="utf-8",
        )

    store = StateStore(tmp_path / "data")
    backend = PersistentFarolKnowledge(store)
    first = tmp_path / "generation-1"
    make_artifact(first, "gen-1", "old.md", "A política antiga vale hoje.", "2026-09-19T23:00:00-03:00", "2026-09-21T03:00:00+03:00")
    FarolArtifactImporter(backend).import_package("generation-business", first)
    source = backend.list_sources("generation-business")[0]
    assert source["valid_from"] == "2026-09-20T02:00:00+00:00"
    assert source["valid_until"] == "2026-09-21T00:00:00+00:00"

    second = tmp_path / "generation-2"
    make_artifact(second, "gen-2", "new.md", "A política nova vale hoje.", "2026-09-19T00:00:00Z", "2026-09-22T00:00:00Z")
    FarolArtifactImporter(backend).import_package("generation-business", second)
    assert all("antiga" not in item["content"] for item in backend.search("generation-business", "política antiga", 5))
    assert backend.search("generation-business", "política nova", 5)


def test_owner_discovery_checkpoint_resumes_without_repeating_answers(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    manager = ConfigurationManager(store)
    started = manager.start("resume", template="physical", materials=["preço do catálogo aprovado"])
    manager.answer(started["session_id"], "Camiseta Azul")

    resumed = ConfigurationManager(StateStore(tmp_path / "data")).status(started["session_id"])
    assert resumed["answered_question_ids"] == ["offer"]
    assert resumed["next_question_index"] == 1
    assert resumed["document_findings"]

    for answer in ("checkout", "catálogo", "preparar sem cobrar"):
        manager.answer(started["session_id"], answer)
    package = manager.finalize(started["session_id"])
    assert package["owner_configuration"]["session_id"] == started["session_id"]
    assert package["lifecycle"] == "draft"
    assert package["sources"] == []
    assert package["capabilities"]["quote"]["state"] == "pending"
    assert package["capabilities"]["human_transfer"]["state"] == "pending"
    assert "price" not in package["offers"][0]
    assert store.get_business("resume")["business"]["id"] == "resume"
    assert store.list_business_versions("resume")[0]["version"] == 1
    assert manager.finalize(started["session_id"]) == package
    assert len(store.list_business_versions("resume")) == 1
    assert manager.status(started["session_id"])["capabilities"]["quote"] == "pending"


def test_owner_can_defer_a_non_blocking_decision_and_fill_it_later(tmp_path: Path):
    manager = ConfigurationManager(StateStore(tmp_path / "data"))
    started = manager.start("defer", template="physical")
    deferred = manager.answer(started["session_id"], "não sei")

    assert deferred["status"] == "in_progress"
    assert deferred["deferred_question_ids"] == ["offer"]
    resolved = manager.answer(started["session_id"], "Camiseta Azul", question_id="offer")
    assert resolved["deferred_question_ids"] == []
    assert resolved["facts"]["offer"] == "Camiseta Azul"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")
def test_state_directory_and_database_are_private(tmp_path: Path):
    store = StateStore(tmp_path / "data")

    assert store.data_dir.stat().st_mode & 0o777 == 0o700
    assert store.db_path.stat().st_mode & 0o777 == 0o600


def test_conversation_compare_and_swap_rejects_stale_worker(tmp_path: Path):
    first_store = StateStore(tmp_path / "data")
    seed_examples(first_store)
    second_store = StateStore(tmp_path / "data")
    first = first_store.load_conversation("azul-b2c", "conversation", "verified:test")
    second = second_store.load_conversation("azul-b2c", "conversation", "verified:test")
    first["version"] = 1
    second["version"] = 1
    first["summary"] = "first worker"
    second["summary"] = "stale worker"

    assert first_store.save_conversation_if_version(first, 0) is True
    assert second_store.save_conversation_if_version(second, 0) is False
    assert second_store.load_conversation("azul-b2c", "conversation", "verified:test")["summary"] == "first worker"


@pytest.mark.parametrize("price", [-1, float("nan"), True, "79"])
def test_package_rejects_unsafe_fixed_prices(price):
    from sales_agent.config import example_package

    package = example_package("physical")
    package["offers"][0]["price"] = price

    with pytest.raises(PackageError):
        validate_package(package)


def test_package_allows_a_free_fixed_offer():
    from sales_agent.config import example_package

    package = example_package("digital")
    package["offers"][0]["price"] = 0

    assert validate_package(package)["offers"][0]["price"] == 0


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("business", "buyer_types"), ["B2C", 7]),
        (("policies",), "permitir tudo"),
        (("offers", 0, "aliases"), ["curso", 7]),
        (("offers", 0, "quote_validity_minutes"), -1),
    ],
)
def test_package_rejects_malformed_structured_fields(path, value):
    from sales_agent.config import example_package

    package = example_package("digital")
    target = package
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value

    with pytest.raises(PackageError):
        validate_package(package)


def test_package_rejects_duplicate_source_versions():
    from sales_agent.config import example_package

    package = example_package("digital")
    package["sources"].append(dict(package["sources"][0]))

    with pytest.raises(PackageError, match="fonte duplicada"):
        validate_package(package)


def test_draft_package_cannot_enable_operational_capability():
    package = example_package("digital")
    package["lifecycle"] = "draft"

    with pytest.raises(PackageError, match="rascunho não pode habilitar"):
        validate_package(package)


def test_draft_package_cannot_enable_human_transfer():
    package = example_package("digital")
    package["lifecycle"] = "draft"
    for capability in package["capabilities"].values():
        capability["state"] = "pending"
        capability["reason"] = "aguardando revisão"
    package["capabilities"]["human_transfer"] = {"state": "assisted", "reason": "fila ainda não aprovada"}

    with pytest.raises(PackageError, match="human_transfer"):
        validate_package(package)


def test_reviewed_draft_promotion_requires_active_lifecycle_and_new_version(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    manager = ConfigurationManager(store)
    started = manager.start("promotion", template="digital")
    for answer in ("Oferta fictícia", "checkout", "catálogo", "preparar"):
        manager.answer(started["session_id"], answer)
    draft = manager.finalize(started["session_id"])
    unchanged = deepcopy(draft)
    unchanged["lifecycle"] = "active"
    with pytest.raises(PackageError, match="package_version"):
        promote_package(store, unchanged)

    reviewed = deepcopy(draft)
    reviewed["lifecycle"] = "active"
    reviewed["package_version"] = "1.0.1"
    promoted = promote_package(store, reviewed)

    assert promoted["lifecycle"] == "active"
    assert promoted["owner_configuration"]["session_id"] == started["session_id"]
    assert [item["version"] for item in store.list_business_versions("promotion")] == [1, 2]


def test_distributed_schemas_accept_public_examples():
    business_schema = json.loads(Path("schemas/business-package.schema.json").read_text(encoding="utf-8"))
    event_schema = json.loads(Path("schemas/channel-event.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(business_schema)
    Draft202012Validator.check_schema(event_schema)
    business_validator = Draft202012Validator(business_schema)

    for template in ("physical", "b2b", "service", "digital"):
        business_validator.validate(example_package(template))
    Draft202012Validator(event_schema).validate(
        {
            "business_id": "negocio-ficticio",
            "conversation_id": "conversa-1",
            "contact_id": "verified:exemplo",
            "channel": "test",
            "event_id": "evento-1",
            "text": "Quero consultar uma oferta fictícia.",
        }
    )


def test_legacy_source_rows_are_marked_for_review_without_lexicographic_selection(tmp_path: Path):
    import hashlib
    import sqlite3

    data_dir = tmp_path / "legacy-source"
    data_dir.mkdir()
    db_path = data_dir / "state.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE businesses (business_id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE knowledge_sources (
                business_id TEXT NOT NULL, source_id TEXT NOT NULL, source_version TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL, locator TEXT NOT NULL, status TEXT NOT NULL,
                origin TEXT NOT NULL, content_hash TEXT NOT NULL, backend TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (business_id, source_id, source_version)
            );
            """
        )
        content = "A condição histórica é de 30 dias."
        db.execute(
            "INSERT INTO knowledge_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-business",
                "policy",
                "z-last",
                "Política histórica",
                content,
                "legacy.md",
                "approved",
                "legacy",
                hashlib.sha256(content.encode()).hexdigest(),
                "sqlite-farol-v1",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        db.commit()

    store = StateStore(data_dir)
    knowledge = PersistentFarolKnowledge(store)
    sources = knowledge.list_sources("legacy-business")
    assert sources[0]["review_status"] == "pending_review"
    assert knowledge.search("legacy-business", "condição", 5) == []
    reviewed = knowledge.review_legacy("legacy-business", "policy", "z-last", "owner reviewed fictional legacy source")
    assert reviewed is True
    assert [item["source_version"] for item in knowledge.search("legacy-business", "condição", 5)] == ["z-last"]


def test_legacy_reimport_keeps_explicit_review_and_owner_revocation(tmp_path: Path):
    artifact = tmp_path / "legacy-artifact"
    documents = artifact / "rag" / "documents"
    documents.mkdir(parents=True)
    (documents / "policy.md").write_text("A política fictícia vale 30 dias.", encoding="utf-8")
    store = StateStore(tmp_path / "data")
    backend = PersistentFarolKnowledge(store)
    importer = FarolArtifactImporter(backend)

    importer.import_package("legacy-reimport", artifact)
    source = backend.list_sources("legacy-reimport")[0]
    assert backend.review_legacy("legacy-reimport", source["source_id"], source["source_version"], "revisão fictícia")
    assert backend.search("legacy-reimport", "política", 5)

    importer.import_package("legacy-reimport", artifact)
    assert backend.search("legacy-reimport", "política", 5)
    backend.revoke("legacy-reimport", source["source_id"], source["source_version"])
    importer.import_package("legacy-reimport", artifact)
    assert backend.search("legacy-reimport", "política", 5) == []


def test_stable_farol_status_does_not_claim_unresolved_contract():
    from sales_agent.knowledge import StableFarolAdapter

    status = StableFarolAdapter().status()

    assert status["status"] == "blocked"
    assert status["contract_status"] == "unresolved"
    assert status["contract"] is None
    assert status["production_claim"] is False
