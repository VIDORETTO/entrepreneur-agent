import json
import urllib.error

import pytest

from sales_agent.config import example_package
from sales_agent.model import HTTPModelAdapter
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
        return FakeResponse(_envelope({"intent": "greeting", "facts": {}}))

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

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse(b"x" * 2049))
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
