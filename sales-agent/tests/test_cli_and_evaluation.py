import json
import re
from pathlib import Path

import pytest

import sales_agent
from sales_agent.cli import main
from sales_agent.config import load_manifest
from sales_agent.evaluation import EvaluationRunner, model_contract_check
from sales_agent.storage import StateStore


def test_model_contract_check_is_explicitly_passed():
    result = model_contract_check()
    assert result["passed"] is True
    assert result["model"] == "untrusted-invalid-actions"


def test_model_selection_is_used_by_evaluate_and_model_check(tmp_path, capsys):
    assert main(["model-check", "--model", "rules-v1"]) == 0
    model_check = json.loads(capsys.readouterr().out)
    assert model_check["model"] == "rules-v1"
    assert model_check["passed"] is True

    assert main(
        ["--data-dir", str(tmp_path / "evaluation"), "evaluate", "--model", "untrusted-invalid-actions"]
    ) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["model"]["name"] == "untrusted-invalid-actions"
    assert report["evaluation"]["thresholds_met"] is False


def test_evaluation_latency_threshold_participates_in_eligibility(tmp_path, monkeypatch):
    monkeypatch.setattr(EvaluationRunner, "MAX_LATENCY_MS", 0)

    report = EvaluationRunner(tmp_path / "evaluation").run()

    assert report["evaluation"]["performance"]["latency_met"] is False
    assert report["evaluation"]["thresholds_met"] is False


def test_evaluation_executes_all_contract_scenarios(tmp_path):
    report = EvaluationRunner(tmp_path / "evaluation").run()

    assert report["summary"] == {"total": 38, "passed": 38, "failed": 0, "critical_failures": 0}
    assert report["evidence_class"] == "simulated-contract-and-persistent-local-backend"
    assert report["backend"]["upstream_farol_rag"] == "not-executed"
    assert report["run"]["package_version"] == sales_agent.__version__
    assert report["run"]["python"]
    assert set(report["run"]["source"]) == {"revision", "dirty"}


def test_evaluation_report_declares_versioned_golden_set_thresholds_and_external_status(tmp_path):
    report = EvaluationRunner(tmp_path / "evaluation").run()

    assert report["evaluation"]["golden_set_version"]
    assert report["evaluation"]["thresholds"]["critical_failures"] == 0
    assert report["evaluation"]["external_execution"]["status"] == "not-executed"
    assert all("duration_ms" in case for case in report["cases"])


def test_split_corpus_repeats_and_reports_distribution(tmp_path):
    dev = EvaluationRunner(tmp_path / "dev", split="dev", repeat=4).run()
    holdout = EvaluationRunner(tmp_path / "holdout", split="holdout", repeat=4).run()

    assert dev["summary"]["total"] >= 50
    assert holdout["summary"]["total"] >= 30
    assert dev["summary"]["failed"] == holdout["summary"]["failed"] == 0
    assert dev["summary"]["total"] + holdout["summary"]["total"] == 80
    assert dev["evaluation"]["pass_at_1"]["denominator"] == dev["summary"]["total"] * 4
    assert dev["evaluation"]["pass_power_k"]["denominator"] == dev["summary"]["total"]
    assert all(case["pass_power_k"]["denominator"] == 1 for case in holdout["cases"])
    assert holdout["evaluation"]["holdout_sha256"]
    assert dev["evaluation"]["holdout_sha256"] is None
    assert holdout["evaluation"]["distribution"] == {
        "direct": 6, "price": 5, "combination": 7, "memory": 5,
        "actions": 3, "human": 3, "installation": 1,
    }
    assert {name: dev["evaluation"]["distribution"].get(name, 0) + holdout["evaluation"]["distribution"].get(name, 0)
            for name in holdout["evaluation"]["distribution"]} == {
        "direct": 16, "price": 12, "combination": 12, "memory": 12,
        "actions": 12, "human": 8, "installation": 8,
    }


def test_holdout_change_is_detected_with_copied_corpus(tmp_path):
    source = Path("evaluation")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for name in ("golden_set.json", "dev.json", "holdout.json", "thresholds.json"):
        (corpus / name).write_bytes((source / name).read_bytes())
    initial = EvaluationRunner(tmp_path / "first", split="holdout", corpus_dir=corpus).run()
    document = json.loads((corpus / "holdout.json").read_text())
    document["cases"][0]["turns"][0]["text"] += " por favor"
    (corpus / "holdout.json").write_text(json.dumps(document))
    changed = EvaluationRunner(
        tmp_path / "second", split="holdout", corpus_dir=corpus,
        previous_report=initial,
    ).run()
    assert changed["evaluation"]["holdout_changed"] is True
    assert changed["evaluation"]["thresholds_met"] is False


def test_any_critical_repeat_failure_blocks_thresholds(tmp_path):
    from sales_agent.model import RuleBasedModel
    from sales_agent.types import Proposal

    class FlakyModel:
        name = "flaky-test"
        calls = 0

        def propose(self, text, package, state):
            self.calls += 1
            if self.calls == 4:
                return Proposal("other", None, model_name=self.name)
            return RuleBasedModel().propose(text, package, state)

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "holdout.json").write_text(json.dumps({"version": "test", "cases": [
        {"id": "flaky", "category": "direct", "business_id": "azul-b2c",
         "critical": True, "initial_state": "fresh", "allowed_operations": ["prepare_checkout"],
         "evidence": "public_result_and_trace",
         "turns": [{"text": "Quero comprar a camiseta azul tamanho M, 1 unidade para SP."}],
         "expected": {"action_type": "prepare_checkout"}, "forbidden": {"action_types": ["charge"]}}
    ]}))
    (corpus / "thresholds.json").write_text(json.dumps({"critical_failures": 0, "minimum_pass_rate": 0.0, "max_latency_ms": 10000}))
    report = EvaluationRunner(tmp_path / "runs", split="holdout", repeat=4, corpus_dir=corpus,
                              model_adapter=FlakyModel()).run()
    assert report["cases"][0]["pass_at_1"] == {"numerator": 3, "denominator": 4, "rate": 0.75}
    assert report["cases"][0]["pass_power_k"] == {"numerator": 0, "denominator": 1, "rate": 0.0}
    assert report["evaluation"]["thresholds_met"] is False


def test_validate_fails_when_no_business_is_installed(tmp_path, capsys):
    exit_code = main(["--data-dir", str(tmp_path / "empty"), "validate"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["valid"] is False
    assert payload["packages"] == []


def test_release_versions_and_embedded_manifest_are_in_sync():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    repository_manifest = json.loads(Path("manifest.json").read_text(encoding="utf-8"))
    embedded_manifest = json.loads(Path("src/sales_agent/resources/manifest.json").read_text(encoding="utf-8"))

    assert project_version
    assert repository_manifest == embedded_manifest
    assert load_manifest() == repository_manifest
    assert sales_agent.__version__ == repository_manifest["version"] == project_version.group(1)


def test_cli_reports_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == "vendedor %s" % sales_agent.__version__


def test_cli_attaches_persisted_supervisor_mode(tmp_path, capsys):
    data_dir = str(tmp_path / "state")
    assert main(["--data-dir", data_dir, "init", "--examples"]) == 0
    capsys.readouterr()
    assert main(["--data-dir", data_dir, "supervisor", "configure", "--mode", "observation"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "observation"

    assert main(
        [
            "--data-dir",
            data_dir,
            "chat",
            "--business-id",
            "azul-b2c",
            "--conversation-id",
            "supervised-cli",
            "--contact-id",
            "verified:teste",
            "--event-id",
            "supervised-1",
            "--message",
            "Quanto custa a camiseta azul?",
            "--json",
        ]
    ) == 0
    assert "79" in json.loads(capsys.readouterr().out)["response"]
    assert main(["--data-dir", data_dir, "supervisor", "list"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1


def test_cli_human_pause_needs_explicit_resume_command(tmp_path, capsys):
    data_dir = str(tmp_path / "state")
    assert main(["--data-dir", data_dir, "init", "--examples"]) == 0
    capsys.readouterr()
    assert main(
        [
            "--data-dir",
            data_dir,
            "chat",
            "--business-id",
            "azul-b2c",
            "--conversation-id",
            "resume-cli",
            "--contact-id",
            "verified:cli",
            "--event-id",
            "resume-1",
            "--message",
            "Quero falar com uma pessoa.",
            "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["state"]["status"] == "human_paused"
    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "conversation",
                "resume",
                "--business-id",
                "azul-b2c",
                "--conversation-id",
                "resume-cli",
                "--contact-id",
                "verified:cli",
                "--authority",
                "operator",
                "--reason",
                "fila liberada",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["resumed"] is True


def test_cli_reconciles_unknown_outbox_without_requeue(tmp_path, capsys):
    data_dir = str(tmp_path / "state")
    store = StateStore(data_dir)
    assert store.enqueue_message("unknown-cli", "business", "conversation", {"response": "fictícia"})
    claimed = store.claim_outbox(limit=1, lease_seconds=1, now="2099-01-01T00:00:00+00:00")[0]
    assert claimed["message_key"] == "unknown-cli"
    assert store.recover_expired_outbox(now="2099-01-01T00:00:02+00:00") == 1

    assert main(
        [
            "--data-dir",
            data_dir,
            "outbox",
            "reconcile",
            "unknown-cli",
            "--resolution",
            "sent",
            "--details",
            '{"provider":{"provider_id":"fake-message-1"},"reason":"contract confirmation"}',
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "sent"
    assert StateStore(data_dir).list_outbox("pending") == []


def test_cli_happy_path_uses_persistent_fictional_state(tmp_path, capsys):
    data_dir = str(tmp_path / "state")

    assert main(["--data-dir", data_dir, "init", "--examples"]) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["businesses"] == ["azul-b2c", "nuvem-b2b", "reforma-consultiva", "curso-digital"]

    assert main(["--data-dir", data_dir, "doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert main(["--data-dir", data_dir, "validate"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    assert main(["--data-dir", data_dir, "knowledge", "query", "--business-id", "azul-b2c", "camiseta"]) == 0
    knowledge = json.loads(capsys.readouterr().out)
    assert knowledge["hits"][0]["business_id"] == "azul-b2c"

    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "chat",
                "--business-id",
                "azul-b2c",
                "--conversation-id",
                "cli-test",
                "--contact-id",
                "verified:teste",
                "--event-id",
                "evento-1",
                "--message",
                "Quero comprar a camiseta azul tamanho G, uma unidade para SP.",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["action"]["type"] == "prepare_checkout"
    assert result["action"]["charged"] is False

    assert main(["--data-dir", data_dir, "outbox", "claim", "--limit", "1"]) == 0
    claimed = json.loads(capsys.readouterr().out)["items"]
    assert claimed[0]["status"] == "processing"
    assert main(["--data-dir", data_dir, "outbox", "ack", claimed[0]["message_key"]]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "sent"

    assert main(["--data-dir", data_dir, "effects", "list", "--status", "confirmed"]) == 0
    effects = json.loads(capsys.readouterr().out)
    assert effects["items"][0]["kind"] == "checkout"
    assert main(["--data-dir", data_dir, "storage", "check"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    backup = tmp_path / "cli-backup.sqlite3"
    assert main(["--data-dir", data_dir, "storage", "backup", str(backup)]) == 0
    assert backup.is_file()
    capsys.readouterr()
    safety = tmp_path / "cli-before-restore.sqlite3"
    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "storage",
                "restore",
                str(backup),
                "--backup-current",
                str(safety),
            ]
        )
        == 0
    )
    restored = json.loads(capsys.readouterr().out)
    assert restored["integrity"]["ok"] is True
    assert safety.is_file()

    store = StateStore(data_dir)
    assert store.enqueue_message("cli-retry", "azul-b2c", "cli-test", {"response": "fictícia"})
    assert main(["--data-dir", data_dir, "outbox", "claim", "--limit", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["message_key"] == "cli-retry"
    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "outbox",
                "nack",
                "cli-retry",
                "--error",
                "falha fictícia",
                "--max-attempts",
                "1",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "dead_letter"

    outcome, _ = store.reserve_checkout_effect(
        "checkout:cli-reconcile",
        {"business_id": "azul-b2c", "conversation_id": "cli-reconcile", "quote_id": "q_cli"},
        business_id="azul-b2c",
        offer_id="camiseta-azul",
        variant="P",
        quantity=1,
    )
    assert outcome == "reserved"
    store.update_effect("checkout:cli-reconcile", "unknown", {"reason": "timeout fictício"})
    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "effects",
                "reconcile",
                "checkout:cli-reconcile",
                "--resolution",
                "failed",
                "--details",
                '{"resolution_source":"teste CLI"}',
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert store.inventory("azul-b2c", "camiseta-azul", "P") == 2


def test_cli_configuration_resumes_and_errors_are_structured(tmp_path, capsys):
    data_dir = str(tmp_path / "state")
    assert main(["--data-dir", data_dir, "configure", "start", "--business-id", "config-test"]) == 0
    session_id = json.loads(capsys.readouterr().out)["session_id"]

    for answer in ("Oferta fictícia", "checkout", "catálogo aprovado", "preparar sem cobrar"):
        assert main(["--data-dir", data_dir, "configure", "answer", session_id, answer]) == 0
        capsys.readouterr()
    assert main(["--data-dir", data_dir, "configure", "finalize", session_id]) == 0
    assert json.loads(capsys.readouterr().out)["finalized"] is True
    exported_path = tmp_path / "draft-package.json"
    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "export-package",
                "--business-id",
                "config-test",
                "--output",
                str(exported_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    exported = json.loads(exported_path.read_text(encoding="utf-8"))
    assert exported["lifecycle"] == "draft"
    assert exported["capabilities"]["quote"]["state"] == "pending"
    exported["lifecycle"] = "active"
    exported["package_version"] = "1.0.1"
    exported_path.write_text(json.dumps(exported), encoding="utf-8")
    assert main(["--data-dir", data_dir, "promote-package", str(exported_path)]) == 0
    assert json.loads(capsys.readouterr().out)["lifecycle"] == "active"

    assert (
        main(
            [
                "--data-dir",
                data_dir,
                "chat",
                "--business-id",
                "inexistente",
                "--conversation-id",
                "c1",
                "--contact-id",
                "verified:teste",
                "--event-id",
                "e1",
                "--message",
                "Olá",
            ]
        )
        == 2
    )
    error = json.loads(capsys.readouterr().err)
    assert error["ok"] is False
    assert "não configurado" in error["error"]
