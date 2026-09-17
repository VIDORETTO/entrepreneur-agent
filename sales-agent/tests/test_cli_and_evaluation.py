import json

from sales_agent.evaluation import EvaluationRunner, model_contract_check


def test_model_contract_check_is_explicitly_passed():
    result = model_contract_check()
    assert result["passed"] is True
    assert result["model"] == "untrusted-invalid-actions"


def test_evaluation_executes_all_contract_scenarios(tmp_path):
    report = EvaluationRunner(tmp_path / "evaluation").run()

    assert report["summary"] == {"total": 38, "passed": 38, "failed": 0, "critical_failures": 0}
    assert report["evidence_class"] == "simulated-contract-and-persistent-local-backend"
    assert report["backend"]["upstream_farol_rag"] == "not-executed"
