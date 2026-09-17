from pathlib import Path

from sales_agent.config import ConfigurationManager, seed_examples
from sales_agent.knowledge import FarolArtifactImporter, PersistentFarolKnowledge
from sales_agent.storage import StateStore


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


def test_farol_artifact_import_uses_persistent_adapter(tmp_path: Path):
    artifact = tmp_path / "farol-package"
    (artifact / "rag" / "documents").mkdir(parents=True)
    (artifact / "rag" / "documents" / "guide.md").write_text("O acesso dura 30 dias.", encoding="utf-8")
    store = StateStore(tmp_path / "data")
    backend = PersistentFarolKnowledge(store)

    count = FarolArtifactImporter(backend).import_package("artifact-business", artifact)
    hits = backend.search("artifact-business", "acesso dura", 5)

    assert count == 1
    assert hits[0]["backend"] == "farol-artifact-v1"
    assert hits[0]["locator"] == "guide.md"


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
    assert store.get_business("resume")["business"]["id"] == "resume"
    assert store.list_business_versions("resume")[0]["version"] == 1


def test_owner_can_defer_a_non_blocking_decision_and_fill_it_later(tmp_path: Path):
    manager = ConfigurationManager(StateStore(tmp_path / "data"))
    started = manager.start("defer", template="physical")
    deferred = manager.answer(started["session_id"], "não sei")

    assert deferred["status"] == "in_progress"
    assert deferred["deferred_question_ids"] == ["offer"]
    resolved = manager.answer(started["session_id"], "Camiseta Azul", question_id="offer")
    assert resolved["deferred_question_ids"] == []
    assert resolved["facts"]["offer"] == "Camiseta Azul"
