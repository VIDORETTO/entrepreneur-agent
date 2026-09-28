"""Public retrieval behavior against a temporary SQLite store."""

from sales_agent.knowledge import PersistentFarolKnowledge
from sales_agent.storage import StateStore


def test_ac031_accent_and_case_retrieve_same_source(tmp_path):
    knowledge = PersistentFarolKnowledge(StateStore(tmp_path))
    knowledge.ingest("shop", "warranty", "v1", "garantia de 30 dias", title="Garantia")

    for query in ("garantía", "GARANTIA"):
        hits = knowledge.search("shop", query, 5)
        assert [hit["source_id"] for hit in hits] == ["warranty"]


def test_ac032_governance_filters_are_applied_before_ranking(tmp_path):
    knowledge = PersistentFarolKnowledge(StateStore(tmp_path))
    common = "Política de garantia de 30 dias"
    knowledge.ingest("shop", "allowed", "v1", common, audience="buyer", active=True)
    knowledge.ingest("shop", "revoked", "v1", common, audience="buyer", active=True)
    knowledge.ingest("other", "foreign", "v1", common, audience="buyer", active=True)
    knowledge.ingest("shop", "expired", "v1", common, audience="buyer", active=True,
                     valid_until="2000-01-01T00:00:00+00:00")
    knowledge.ingest("shop", "internal", "v1", common, audience="internal", active=True)
    knowledge.store.revoke_source("shop", "revoked")

    hits = knowledge.search("shop", "garantia", audience="buyer")
    assert [hit["source_id"] for hit in hits] == ["allowed"]
    assert knowledge.search("shop", "!!?") == []


def test_ac033_fts5_p95_under_50ms_for_5000_sources(tmp_path):
    import hashlib
    import math
    import time

    import pytest

    store = StateStore(tmp_path)
    if not store.fts5_available():
        pytest.skip("SQLite was built without FTS5")
    sources = []
    for index in range(5000):
        content = f"Produto sintético codigo{index:04d} com instruções de garantia fictícia."
        sources.append({
            "business_id": "scale", "source_id": f"snippet-{index:04d}",
            "source_version": "v1", "title": f"Item codigo{index:04d}",
            "content": content, "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "active": True,
        })
    store.put_sources_atomic(sources)
    knowledge = PersistentFarolKnowledge(store)
    elapsed = []
    for index in range(100):
        started = time.perf_counter()
        hits = knowledge.search("scale", f"codigo{index * 50:04d}")
        elapsed.append((time.perf_counter() - started) * 1000)
        assert hits[0]["source_id"] == f"snippet-{index * 50:04d}"
    assert sorted(elapsed)[math.ceil(len(elapsed) * .95) - 1] < 50


def test_ac034_retrieval_set_reports_recall_and_abstention(tmp_path):
    from sales_agent.evaluation import EvaluationRunner

    runner = EvaluationRunner(tmp_path / "evaluation", split="dev")
    result = runner.evaluate_retrieval()
    assert result["version"] == "2026-09-28.1"
    assert result["recall_at_5"] == {"hit": 32, "total": 32, "rate": 1.0}
    assert result["abstention"] == {"correct": 8, "total": 8, "rate": 1.0}
