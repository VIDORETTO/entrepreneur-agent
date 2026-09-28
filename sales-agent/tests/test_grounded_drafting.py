"""Buyer-visible drafting stays behind deterministic claims and state."""

import json
from types import SimpleNamespace

import pytest

from sales_agent.config import seed_examples, seed_package
from sales_agent.conversation import SellerEngine
from sales_agent.drafting import ResponseRequirements
from sales_agent.model import HTTPModelAdapter, RuleBasedModel
from sales_agent.storage import StateStore


class ScriptedDrafter:
    name = "scripted-drafter"

    def __init__(self, *drafts):
        self.drafts = list(drafts)
        self.calls = []

    def propose(self, text, package, state):
        return RuleBasedModel().propose(text, package, state)

    def draft_response(self, requirements, feedback):
        self.calls.append((requirements, feedback))
        return self.drafts.pop(0)


def _engine(tmp_path, drafter):
    store = StateStore(tmp_path)
    seed_examples(store)
    package = store.get_business("azul-b2c")
    package["draft_mode"] = "on"
    package["offers"][0]["price"] = 79.90
    seed_package(store, package)
    return SellerEngine(store, model=drafter)


def _send(engine, text):
    return engine.handle({
        "business_id": "azul-b2c", "conversation_id": "draft-test",
        "contact_id": "verified:test", "channel": "test", "event_id": "draft-1", "text": text,
    })


def test_supported_natural_draft_reaches_buyer(tmp_path):
    drafter = ScriptedDrafter("Fica R$ 79,90 com frete para SP.")
    result = _send(_engine(tmp_path, drafter), "Quanto custa a camiseta azul?")

    assert result.response == "Fica R$ 79,90 com frete para SP."
    assert any(item["type"] == "draft_accepted" for item in result.trace)
    assert len(drafter.calls) == 1


def test_unsupported_discount_twice_returns_template(tmp_path):
    drafter = ScriptedDrafter("Hoje tem 10% de desconto.", "Hoje tem 10% de desconto.")
    result = _send(_engine(tmp_path, drafter), "Quanto custa a camiseta azul?")

    assert result.response.startswith("O Camiseta Azul custa R$ 79.90")
    assert [item["type"] for item in result.trace].count("claim_unsupported") == 2
    assert result.trace[-1] == {"type": "draft_fallback", "reason": "verification_failed"}
    assert len(drafter.calls) == 2


def test_draft_without_necessary_variant_question_is_rejected(tmp_path):
    drafter = ScriptedDrafter("Temos a camiseta azul disponível.", "Temos a camiseta azul disponível.")
    result = _send(_engine(tmp_path, drafter), "Quero a camiseta azul.")

    assert "tamanho" in result.response.casefold()
    assert result.state["pending"]["field"] == "variant"
    assert any(item["type"] == "claim_unsupported" and any(
        claim["kind"] == "necessary_question" for claim in item["claims"]
    ) for item in result.trace)


def test_draft_omitting_asked_duration_is_rejected(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    package = store.get_business("curso-digital")
    package["draft_mode"] = "on"
    seed_package(store, package)
    drafter = ScriptedDrafter("Você terá acesso ao curso.", "Você terá acesso ao curso.")
    result = SellerEngine(store, model=drafter).handle({
        "business_id": "curso-digital", "conversation_id": "draft-duration",
        "contact_id": "verified:test", "channel": "test", "event_id": "draft-duration-1",
        "text": "Como funciona o acesso e por quanto tempo ele dura?",
    })

    assert "12 meses" in result.response
    assert any(item["type"] == "claim_unsupported" and any(
        claim == {"kind": "topic_missing", "value": "duration"} for claim in item["claims"]
    ) for item in result.trace)


def test_unapproved_checkout_url_never_reaches_buyer(tmp_path):
    drafter = ScriptedDrafter(
        "Conclua aqui: https://pague-aqui.example",
        "Conclua aqui: https://pague-aqui.example",
    )
    result = _send(
        _engine(tmp_path, drafter),
        "Manda o link da camiseta azul tamanho M, uma unidade para SP.",
    )

    assert result.action["type"] == "prepare_checkout"
    assert result.action["url"] in result.response
    assert "pague-aqui.example" not in result.response
    assert any(item["type"] == "claim_unsupported" and any(
        claim["kind"] == "url" for claim in item["claims"]
    ) for item in result.trace)


@pytest.mark.parametrize("draft,kind", [
    ("A camiseta chega em 2 dias e custa R$ 79,90.", "deadline"),
    ("O pacote inclui 4 unidades por R$ 79,90.", "quantity"),
])
def test_unapproved_duration_or_quantity_falls_back(tmp_path, draft, kind):
    result = _send(_engine(tmp_path, ScriptedDrafter(draft, draft)), "Quanto custa a camiseta azul?")

    assert result.response.startswith("O Camiseta Azul custa R$ 79.90")
    assert any(item["type"] == "claim_unsupported" and any(
        claim["kind"] == kind for claim in item["claims"]
    ) for item in result.trace)


def test_http_drafter_keeps_trusted_instructions_separate_from_buyer(monkeypatch):
    adapter = HTTPModelAdapter("http://127.0.0.1:1/v1/chat/completions", "fictional-key", "fake-model")
    captured = []

    def fake_send(request):
        captured.append(json.loads(request.data))
        return {"choices": [{"message": {"content": "Fica R$ 79,90."}}]}

    monkeypatch.setattr(adapter, "_send", fake_send)
    requirements = ResponseRequirements.from_result(
        "Quanto custa a camiseta azul?",
        SimpleNamespace(response="A camiseta custa R$ 79,90.", evidence=[], state={"pending": None}, action=None),
    )
    assert adapter.draft_response(requirements, []) == "Fica R$ 79,90."
    assert captured[0]["messages"][0]["role"] == "system"
    assert "Quanto custa a camiseta azul?" not in captured[0]["messages"][0]["content"]
    assert captured[0]["messages"][1] == {
        "role": "user", "content": "<buyer_message>Quanto custa a camiseta azul?</buyer_message>",
    }
    assert "fictional-key" not in json.dumps(captured[0])


def test_first_invalid_draft_can_be_repaired_once(tmp_path):
    drafter = ScriptedDrafter("Hoje tem 10% de desconto.", "A camiseta fica R$ 79,90.")
    result = _send(_engine(tmp_path, drafter), "Quanto custa a camiseta azul?")

    assert result.response == "A camiseta fica R$ 79,90."
    assert len(drafter.calls) == 2
    assert any(item["type"] == "draft_accepted" and item["attempt"] == 2 for item in result.trace)


def test_disabled_drafting_keeps_template_and_does_not_call_drafter(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    drafter = ScriptedDrafter("Preço inventado: R$ 1,00")
    result = SellerEngine(store, model=drafter).handle({
        "business_id": "azul-b2c", "conversation_id": "draft-off",
        "contact_id": "verified:test", "channel": "test", "event_id": "draft-off-1",
        "text": "Quanto custa a camiseta azul?",
    })

    assert "R$ 79.00" in result.response
    assert drafter.calls == []


@pytest.mark.parametrize("draft,kind", [
    ("O pagamento foi confirmado.", "payment_status"),
    ("O frete é grátis.", "shipping"),
    ("A garantia cobre qualquer defeito.", "policy"),
])
def test_unapproved_status_and_policy_claims_fall_back(tmp_path, draft, kind):
    result = _send(_engine(tmp_path, ScriptedDrafter(draft, draft)), "Quanto custa a camiseta azul?")

    assert result.response.startswith("O Camiseta Azul custa R$ 79.90")
    assert any(item["type"] == "claim_unsupported" and any(
        claim["kind"] == kind for claim in item["claims"]
    ) for item in result.trace)
