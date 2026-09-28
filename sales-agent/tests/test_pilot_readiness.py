"""Readiness gates on an isolated local store."""

from sales_agent.config import seed_examples
from sales_agent.governance import PilotController
from sales_agent.storage import StateStore


def test_ac038_rules_report_does_not_ready_real_pilot(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    controller = PilotController(store)
    report = {"status": "passed", "model": {"name": "rules-v1"},
              "evaluation": {"split": "holdout", "thresholds_met": True}}
    result = controller.readiness("azul-b2c", "chatwoot", evidence={"holdout": report})
    assert result["ready"] is False
    assert "holdout_selected_model" in result["missing"]


def ready_fixture(store):
    from pathlib import Path

    from sales_agent.config import seed_package
    from sales_agent.validation import package_fingerprint

    package = store.get_business("azul-b2c")
    package["service_hours"] = {"timezone": "America/Sao_Paulo", "intervals": {
        "monday": [{"start": "09:00", "end": "18:00"}]}}
    package["privacy"] = {"retention_days": 180}
    seed_package(store, package)
    fingerprint = package_fingerprint(package)
    holdout_hash = Path("evaluation/holdout.sha256").read_text(encoding="ascii").strip()
    holdout_stat = Path("evaluation/holdout.json").stat()
    return {
        "holdout": {"status": "passed", "model": {"name": "fake-remote", "profile": "openai"},
                    "candidate_package_version": package["package_version"],
                    "candidate_package_fingerprint": fingerprint,
                    "evaluation": {"split": "holdout", "thresholds_met": True,
                                   "holdout_sha256": holdout_hash,
                                   "holdout_file": {"size": holdout_stat.st_size,
                                                    "mtime_ns": holdout_stat.st_mtime_ns}}},
        "model_check": {"passed": True, "model": "fake-remote", "profile": "openai"},
        "channel_contract": {"channel": "chatwoot", "signature_mode": "timestamped",
                             "signature_passed": True, "echo_passed": True},
        "interruption": {"status": "passed", "scope_key": "azul-b2c:chatwoot"},
    }


def test_ac039_complete_evidence_is_ready(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    evidence = ready_fixture(store)
    result = PilotController(store).readiness("azul-b2c", "chatwoot", evidence=evidence)
    assert result["ready"] is True
    assert result["missing"] == []
    assert len(result["evidence"]) == 6


def test_ac040_configure_requires_readiness_or_audited_override(tmp_path):
    import pytest

    store = StateStore(tmp_path)
    seed_examples(store)
    controller = PilotController(store)
    common = {"mode": "pilot", "cohort": {"all": True}, "limits": {"max_deliveries": 1},
              "evaluated_package_version": "1.0.0", "authorize": True}
    with pytest.raises(ValueError, match="piloto não pronto"):
        controller.configure("azul-b2c", "chatwoot", **common)
    result = controller.configure("azul-b2c", "chatwoot", **common,
                                  override=True, reason="teste interno")
    assert result["override_reason"] == "teste interno"
    inspected = controller.inspect("azul-b2c", "chatwoot")
    assert inspected["config"]["override_reason"] == "teste interno"
    assert "holdout_selected_model" in inspected["config"]["readiness"]["missing"]


def test_ac040_cli_returns_code_two_without_readiness(tmp_path, capsys):
    from sales_agent.cli import main

    store = StateStore(tmp_path)
    seed_examples(store)
    args = ["--data-dir", str(tmp_path), "pilot", "configure", "--business-id", "azul-b2c",
            "--mode", "pilot", "--cohort", '{"all":true}', "--limits", '{"max_deliveries":1}',
            "--evaluated-package-version", "1.0.0", "--authorize"]
    assert main(args) == 2
    capsys.readouterr()
    assert main(args + ["--override", "--reason", "teste interno"]) == 0
    assert "teste interno" in capsys.readouterr().out


def test_readiness_rejects_stale_package_and_other_model(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    evidence = ready_fixture(store)
    evidence["holdout"]["candidate_package_fingerprint"] = "stale"
    evidence["model_check"]["model"] = "different-model"
    result = PilotController(store).readiness("azul-b2c", "chatwoot", evidence=evidence)
    assert "holdout_selected_model" in result["missing"]
    assert "model_check_selected_profile" in result["missing"]


def test_readiness_uses_digest_without_reading_holdout_corpus(tmp_path, monkeypatch):
    from pathlib import Path

    store = StateStore(tmp_path)
    seed_examples(store)
    evidence = ready_fixture(store)
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path):
        if path.name == "holdout.json":
            raise AssertionError("readiness must not read reserved holdout cases")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    result = PilotController(store).readiness("azul-b2c", "chatwoot", evidence=evidence)
    assert result["ready"] is True


def test_holdout_evaluation_rejects_stale_digest_manifest(tmp_path):
    import pytest

    from sales_agent.evaluation import EvaluationRunner

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "holdout.json").write_text('{"version":"test","cases":[]}', encoding="utf-8")
    (corpus / "holdout.sha256").write_text("0" * 64 + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="hash do holdout"):
        EvaluationRunner(tmp_path / "runs", split="holdout", corpus_dir=corpus).run()


def test_readiness_rejects_stale_holdout_file_metadata(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    evidence = ready_fixture(store)
    evidence["holdout"]["evaluation"]["holdout_file"]["mtime_ns"] -= 1
    result = PilotController(store).readiness("azul-b2c", "chatwoot", evidence=evidence)
    assert "holdout_selected_model" in result["missing"]
