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


def test_evaluation_executes_all_contract_scenarios(tmp_path):
    report = EvaluationRunner(tmp_path / "evaluation").run()

    assert report["summary"] == {"total": 38, "passed": 38, "failed": 0, "critical_failures": 0}
    assert report["evidence_class"] == "simulated-contract-and-persistent-local-backend"
    assert report["backend"]["upstream_farol_rag"] == "not-executed"
    assert report["run"]["package_version"] == sales_agent.__version__
    assert report["run"]["python"]
    assert set(report["run"]["source"]) == {"revision", "dirty"}


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
