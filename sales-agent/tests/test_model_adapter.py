import json
import urllib.error

import pytest

from sales_agent.config import example_package
from sales_agent.conversation import SellerEngine
from sales_agent.model import HTTPModelAdapter, load_model_config
from sales_agent.storage import StateStore
from sales_agent.types import empty_conversation


class FakeResponse:
    def __init__(self, payload, url="https://models.example.test/v1/chat"):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, amount):
        return self.payload[:amount]

    def geturl(self):
        return self.url


def _envelope(proposal):
    return {"choices": [{"message": {"content": json.dumps(proposal)}}]}


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://models.example.test/v1/chat",
        "ftp://models.example.test/v1/chat",
        "https://user:secret@models.example.test/v1/chat",
    ],
)
def test_http_model_adapter_rejects_unsafe_endpoints(endpoint):
    with pytest.raises(ValueError):
        HTTPModelAdapter(endpoint, "fictional-key", "fictional-model")


@pytest.mark.parametrize(
    ("timeout", "max_response_bytes"),
    [(0, 2048), (121, 2048), (15, 1023), (15, 10_000_001)],
)
def test_http_model_adapter_rejects_unbounded_limits(timeout, max_response_bytes):
    with pytest.raises(ValueError, match="limites"):
        HTTPModelAdapter(
            "https://models.example.test/v1/chat",
            "fictional-key",
            "fictional-model",
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )


def test_http_model_adapter_accepts_strict_json_contract(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            _envelope(
                {
                    "intent": "buy",
                    "offer_id": "curso-analise",
                    "facts": {"quantity": 1},
                    "requested_action": "execute",
                }
            )
        ),
    )
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model")

    proposal = adapter.propose(
        "Quero comprar",
        example_package("digital"),
        empty_conversation("curso-digital", "conversation", "verified:test"),
    )

    assert proposal.intent == "buy"
    assert proposal.facts == {"quantity": 1}
    assert proposal.confidence == "external-unverified"


def test_http_model_adapter_preserves_declared_topics(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            _envelope(
                {
                    "intent": "knowledge",
                    "offer_id": "curso-analise",
                    "facts": {},
                    "topics": ["guarantee", "return"],
                }
            )
        ),
    )
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model")

    proposal = adapter.propose(
        "Qual é a garantia e a devolução?",
        example_package("digital"),
        empty_conversation("curso-digital", "conversation", "verified:test"),
    )

    assert proposal.topics == ["guarantee", "return"]


def test_http_model_adapter_receives_only_bounded_buyer_skill_context(monkeypatch):
    captured = {}

    def capture(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse(_envelope({"intent": "greeting", "facts": {}}))

    monkeypatch.setattr("urllib.request.urlopen", capture)
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model")
    package = example_package("digital")
    package["_buyer_skill_context"] = [
        {"id": "seller-conversation", "version": "1", "content": "buyer guidance"}
    ]
    package["_configuration_skill_context"] = [{"id": "sales-business-discovery", "content": "owner-only"}]

    adapter.propose("Olá", package, empty_conversation("curso-digital", "conversation", "verified:test"))

    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][1]["role"] == "user"
    assert "buyer guidance" in captured["messages"][0]["content"]
    assert "<buyer_message>Olá</buyer_message>" == captured["messages"][1]["content"]
    assert "Olá" not in captured["messages"][0]["content"]
    assert "_configuration_skill_context" not in json.dumps(captured)
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_http_model_adapter_repairs_one_invalid_response(monkeypatch):
    calls = []

    def scripted(request, timeout):
        calls.append(json.loads(request.data.decode("utf-8")))
        proposal = {"intent": "not-an-intent", "facts": {}} if len(calls) == 1 else {"intent": "greeting", "facts": {}}
        return FakeResponse(_envelope(proposal))

    monkeypatch.setattr("urllib.request.urlopen", scripted)
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model", fallback="rules")

    result = adapter.propose("Olá", example_package("digital"), {})

    assert result.intent == "greeting"
    assert len(calls) == 2
    assert result.raw["model_calls"] == 2
    assert "intent fora do contrato" in calls[1]["messages"][-1]["content"]


def test_http_model_adapter_falls_back_after_two_invalid_responses(monkeypatch):
    calls = []

    def invalid(request, timeout):
        calls.append(request)
        return FakeResponse(_envelope({"intent": "not-an-intent", "facts": {}}))

    monkeypatch.setattr("urllib.request.urlopen", invalid)
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model", fallback="assist")

    proposal = adapter.propose("Quero comprar", example_package("digital"), {})

    assert len(calls) == 2
    assert proposal.intent == "unknown"
    assert proposal.requested_action is None
    assert proposal.raw["model_contract_failed"] is True
    assert proposal.raw["model_calls"] == 2


def test_contract_failure_in_engine_has_trace_and_no_effect(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(_envelope({"intent": "not-an-intent", "facts": {}})),
    )
    store = StateStore(tmp_path / "data")
    store.save_business(example_package("digital"))
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model", fallback="rules")
    result = SellerEngine(store, model=adapter).handle(
        {
            "business_id": "curso-digital", "conversation_id": "fallback", "contact_id": "verified:test",
            "channel": "test", "event_id": "e1", "text": "Quero comprar o curso agora",
        }
    )

    assert result.action is None
    assert result.state["pending"]["type"] == "model_contract_failed"
    assert any(item["type"] == "model_contract_failed" and item["calls"] == 2 for item in result.trace)


def test_usage_cost_uses_configured_prices(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {**_envelope({"intent": "greeting", "facts": {}}), "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}
        ),
    )
    adapter = HTTPModelAdapter(
        "https://models.example.test/v1/chat", "fictional-key", "fictional-model",
        prices={"input_per_million": 1, "output_per_million": 5},
    )

    result = adapter.propose("Olá", example_package("digital"), {})

    assert result.raw["usage"] == {"prompt_tokens": 1000, "completion_tokens": 200}
    assert result.raw["cost"] == 0.002


@pytest.mark.parametrize("profile", ["openai", "openai-compatible"])
def test_profiles_share_local_contract_and_report_identity(monkeypatch, profile):
    captured = []

    def respond(request, timeout):
        captured.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(_envelope({"intent": "greeting", "facts": {}}))

    monkeypatch.setattr("urllib.request.urlopen", respond)
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model", profile=profile)

    result = adapter.propose("Olá", example_package("digital"), {})

    assert result.intent == "greeting"
    assert result.model_name == "http:fictional-model"
    assert result.raw["profile"] == profile
    schema = captured[0]["response_format"]["json_schema"]
    if profile == "openai":
        assert schema["strict"] is True
    else:
        assert "strict" not in schema


def test_openai_refusal_is_not_interpreted_as_proposal(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse({"choices": [{"message": {"refusal": "cannot comply", "content": None}}]}),
    )
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model", fallback="assist")

    proposal = adapter.propose("Olá", example_package("digital"), {})

    assert proposal.raw["model_contract_failed"] is True
    assert proposal.requested_action is None


def test_model_config_resolves_key_and_prices_without_literal_secret(tmp_path, monkeypatch):
    path = tmp_path / "model.json"
    settings = {
        "profile": "openai", "model": "fictional-model", "api_key": "env:FICTIONAL_MODEL_TOKEN",
        "prices": {"input_per_million": 1, "output_per_million": 5},
    }
    monkeypatch.setenv("FICTIONAL_MODEL_TOKEN", "fictional-key")
    path.write_text(json.dumps(settings), encoding="utf-8")
    loaded = load_model_config(str(path))
    assert loaded["api_key"] == "fictional-key"
    assert loaded["endpoint"] == "https://api.openai.com/v1/chat/completions"
    assert loaded["prices"] == {"input_per_million": 1, "output_per_million": 5}

    settings["api_key"] = "literal-secret"
    path.write_text(json.dumps(settings), encoding="utf-8")
    with pytest.raises(ValueError, match="env:NOME"):
        load_model_config(str(path))


@pytest.mark.parametrize(
    "proposal",
    [
        {"intent": "delete_everything", "facts": {}},
        {"intent": "buy", "facts": "quantity=1"},
        {"intent": "buy", "facts": {}, "offer_id": 123},
    ],
)
def test_http_model_adapter_rejects_contract_violations(monkeypatch, proposal):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(_envelope(proposal)),
    )
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model")

    with pytest.raises(ValueError, match="fora do contrato"):
        adapter.propose("teste", example_package("digital"), {})


def test_http_model_adapter_limits_response_and_retries_transient_failure(monkeypatch):
    attempts = []

    def transient_then_success(request, timeout):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise urllib.error.URLError("simulated")
        return FakeResponse(_envelope({"intent": "greeting", "facts": {}}), url="http://localhost:8000/v1/chat")

    monkeypatch.setattr("urllib.request.urlopen", transient_then_success)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    adapter = HTTPModelAdapter(
        "http://localhost:8000/v1/chat",
        "fictional-key",
        "fictional-model",
        retries=1,
        max_response_bytes=2048,
    )
    assert adapter.propose("Olá", example_package("digital"), {}).intent == "greeting"
    assert len(attempts) == 2

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse(b"x" * 2049, url="http://localhost:8000/v1/chat"))
    with pytest.raises(ValueError, match="excedeu"):
        adapter.propose("Olá", example_package("digital"), {})


def test_http_model_adapter_rejects_redirect_to_plain_http(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            _envelope({"intent": "greeting", "facts": {}}),
            url="http://models.example.test/insecure",
        ),
    )
    adapter = HTTPModelAdapter("https://models.example.test/v1/chat", "fictional-key", "fictional-model")

    with pytest.raises(ValueError, match="redirecionamento"):
        adapter.propose("Olá", example_package("digital"), {})
