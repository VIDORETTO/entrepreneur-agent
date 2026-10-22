"""Natural voice: Brazilian formats, owner voice, bot-copy lint and objections."""

from copy import deepcopy

import pytest

from sales_agent.config import example_package, seed_examples, seed_package
from sales_agent.conversation import SellerEngine
from sales_agent.drafting import brl, commercial_claims, parse_amount
from sales_agent.model import RuleBasedModel
from sales_agent.storage import StateStore
from sales_agent.validation import PackageError, validate_package
from sales_agent.voice import buyer_register, select_examples, style_violations, voice_settings

from .conftest import event
from .test_grounded_drafting import ScriptedDrafter, _engine, _send
from .test_human_access import configured


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1.299,90", "1299.90"), ("79,90", "79.90"), ("79.90", "79.90"), ("79", "79.00"), ("1.299", "1299.00"), ("1,299.00", "1299.00")],
)
def test_amounts_are_canonical_in_brazilian_and_plain_formats(raw, expected):
    assert parse_amount(raw) == expected


def test_brl_uses_brazilian_separators():
    assert brl(1299.9) == "R$ 1.299,90"
    assert brl(79) == "R$ 79,00"


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("Fica setenta e nove reais e noventa centavos.", ("price", "79.90")),
        ("Sai por mil e duzentos reais.", ("price", "1200.00")),
        ("Fica 85 reais.", ("price", "85.00")),
        ("O frete sai de graça para você.", ("shipping", "free_shipping")),
        ("Não cobramos frete.", ("shipping", "free_shipping")),
        ("Chega em três dias.", ("deadline", "3 dias")),
        ("Seu pagamento já foi aprovado.", ("payment_status", "payment_confirmed")),
    ],
)
def test_paraphrased_commercial_claims_are_recognized(text, claim):
    assert claim in commercial_claims(text)


def test_draft_with_thousands_price_in_brazilian_format_is_accepted(tmp_path):
    drafter = ScriptedDrafter("Esse sai por R$ 1.299,90 a unidade, já com tudo que está na descrição.")
    store = StateStore(tmp_path)
    seed_examples(store)
    package = store.get_business("azul-b2c")
    package["draft_mode"] = "on"
    package["offers"][0]["price"] = 1299.90
    seed_package(store, package)

    result = _send(SellerEngine(store, model=drafter), "Quanto custa a camiseta azul?")

    assert result.response.startswith("Esse sai por R$ 1.299,90")
    assert any(item["type"] == "draft_accepted" for item in result.trace)


@pytest.mark.parametrize(
    "draft",
    ["Fica setenta reais a unidade.", "Fica R$ 79,90 e o frete sai de graça.", "Sou uma pessoa de verdade, fica R$ 79,90."],
)
def test_paraphrased_unsupported_claims_fall_back_to_template(tmp_path, draft):
    result = _send(_engine(tmp_path, ScriptedDrafter(draft, draft)), "Quanto custa a camiseta azul?")

    assert result.response.startswith("Camiseta Azul sai por R$ 79,90")
    assert any(item["type"] == "draft_fallback" for item in result.trace)


def test_bot_copy_is_retried_and_natural_retry_is_accepted(tmp_path):
    drafter = ScriptedDrafter(
        "Ótima pergunta! A Camiseta Azul custa R$ 79,90 — posso ajudar em algo mais?",
        "A azul sai por R$ 79,90 cada.",
    )
    result = _send(_engine(tmp_path, drafter), "Quanto custa a camiseta azul?")

    assert result.response == "A azul sai por R$ 79,90 cada."
    rejected = next(item for item in result.trace if item["type"] == "claim_unsupported")
    kinds = {claim["value"] for claim in rejected["claims"]}
    assert "dash" in kinds and "unneeded_question" in kinds
    assert any(value.startswith("phrase:") for value in kinds)


def test_style_lint_respects_owner_voice_and_previous_opening():
    voice = voice_settings({"voice": {"emoji": "none", "forbidden_phrases": ["meu querido"]}})
    found = style_violations(
        "Perfeito, meu querido 😀 fica R$ 10,00.",
        voice,
        template="Fica R$ 10,00.",
        previous_seller=["Perfeito, meu querido, anotado."],
    )
    values = {item["value"] for item in found}
    assert {"emoji", "phrase:meu querido", "repeated_opening"} <= values


def test_style_lint_allows_lists_and_length_the_template_already_needs():
    template = "Opções:\n- P\n- M\n- G\n" + "Detalhe " * 60
    assert style_violations(template, voice_settings({}), template=template) == []


def test_drafter_receives_history_register_and_matching_owner_examples(tmp_path):
    store = StateStore(tmp_path)
    seed_examples(store)
    package = store.get_business("azul-b2c")
    package["draft_mode"] = "on"
    package["voice"]["examples"].append(
        {"situation": "preço da camiseta", "buyer": "qnto ta a camiseta?", "seller": "Tá saindo por esse valor aqui, ó."}
    )
    seed_package(store, package)
    drafter = ScriptedDrafter("Oi! Tudo bem por aqui.", "Camiseta azul: R$ 79,00 a unidade.")
    engine = SellerEngine(store, model=drafter)
    engine.handle(event("azul-b2c", "voice", "e1", "oi"))
    engine.handle(event("azul-b2c", "voice", "e2", "qnto ta a camiseta azul?"))

    requirements = drafter.calls[-1][0]
    assert requirements.history[-1]["buyer"] == "oi"
    assert requirements.history[-1]["seller"]
    assert requirements.register["informal"] is True
    assert requirements.examples[0]["situation"] == "preço da camiseta"


def test_auto_draft_mode_without_drafter_is_silent(app):
    store, engine = app
    result = engine.handle(event("azul-b2c", "auto", "e1", "Quanto custa a camiseta azul?"))

    assert "R$ 79,00" in result.response
    assert not any(item["type"].startswith("draft_") for item in result.trace)


def test_register_mirrors_informal_short_buyer():
    assert buyer_register(["oi", "vc tem a azul?"]) == {"length": "curta", "informal": True, "emoji": False}
    assert buyer_register(["Bom dia. Gostaria de saber as condições de pagamento para pedidos corporativos acima de cinquenta unidades, por favor."])["length"] == "média"


def test_examples_fall_back_to_first_ones_without_overlap():
    voice = {"examples": [{"situation": "a", "seller": "x"}, {"situation": "b", "seller": "y"}]}
    assert [item["seller"] for item in select_examples(voice, "zzz", k=1)] == ["x"]


@pytest.mark.parametrize(
    "voice",
    [
        {"emoji": "lots"},
        {"address": "senhor"},
        {"max_chars": 10},
        {"examples": [{"buyer": "oi"}]},
        {"unknown": True},
        {"disclose_ai": "sim"},
    ],
)
def test_invalid_voice_is_rejected(voice):
    package = deepcopy(example_package("physical"))
    package["voice"] = voice
    with pytest.raises(PackageError):
        validate_package(package)


def test_offer_question_override_must_be_a_question():
    package = deepcopy(example_package("service"))
    package["offers"][0]["questions"] = {"scope": "Diga o escopo."}
    with pytest.raises(PackageError, match="questions"):
        validate_package(package)


def test_offer_question_override_is_used(app):
    _, engine = app
    result = engine.handle(event("reforma-consultiva", "scope", "e1", "Quero reformar minha cozinha. Quanto sai?"))
    assert result.response == "Você quer uma reforma completa ou só trocar os revestimentos?"


def test_price_objection_offers_real_cheaper_alternative_without_discount(tmp_path):
    result = _two_offers(tmp_path).handle(event("azul-b2c", "obj", "e1", "A camiseta azul está cara."))

    assert "R$ 79,00" in result.response
    assert "desconto" in result.response.casefold()
    assert "Camiseta Básica sai por R$ 49,00" in result.response
    assert not result.action
    assert any(item["type"] == "objection_alternative" for item in result.trace)


def test_buyer_who_wants_time_is_not_pushed(app):
    _, engine = app
    result = engine.handle(event("azul-b2c", "think", "e1", "Vou pensar e depois te falo."))

    assert not result.action
    assert "?" not in result.response
    assert "sem pressa" in result.response
    assert not any(word in result.response.casefold() for word in ("desconto", "última", "hoje", "garanta"))


def _two_offers(tmp_path):
    store = StateStore(tmp_path)
    package = deepcopy(example_package("physical"))
    package["offers"].append({**deepcopy(package["offers"][0]), "id": "camiseta-basica", "name": "Camiseta Básica",
                              "aliases": ["camiseta básica"], "price": 49.0})
    seed_package(store, package)
    return SellerEngine(store)


def test_price_objection_without_offer_asks_which_product(tmp_path):
    result = _two_offers(tmp_path).handle(event("azul-b2c", "obj-none", "e1", "Achei caro."))
    assert "qual produto" in result.response.casefold()


@pytest.mark.parametrize("text", ["Você é um robô?", "to falando com uma pessoa?", "vc é humano?"])
def test_assistant_discloses_it_is_not_a_person(app, text):
    _, engine = app
    result = engine.handle(event("azul-b2c", "who", "e1", text))

    assert "virtual" in result.response
    assert result.state.get("status") != "human_paused"
    assert any(item["type"] == "ai_disclosed" for item in result.trace)


def test_explicit_request_for_a_person_still_transfers():
    proposal = RuleBasedModel().propose("Você é robô? Quero falar com uma pessoa", example_package("physical"), {})
    assert proposal.intent == "human"


def test_greeting_introduces_virtual_assistant(app):
    _, engine = app
    result = engine.handle(event("azul-b2c", "hello", "e1", "Oi"))
    assert "atendimento virtual" in result.response


def test_after_hours_names_next_weekday_in_portuguese(tmp_path):
    hours = {"timezone": "America/Sao_Paulo", "intervals": {"monday": [{"start": "09:00", "end": "18:00"}]}}
    _, engine, package, _ = configured(tmp_path, instant="2026-09-30T02:00:00+00:00", hours=hours)
    result = engine.handle(event(package["business"]["id"], "weekday", "e1", "Quero falar com uma pessoa"))
    assert "segunda às 9h" in result.response


def test_engine_templates_avoid_bot_copy(app):
    _, engine = app
    voice = voice_settings({})
    messages = ["Oi", "Quanto custa a camiseta azul?", "Está caro", "Vou pensar", "obrigado", "Quero falar com uma pessoa"]
    for index, text in enumerate(messages):
        result = engine.handle(event("azul-b2c", "lint", "e%d" % index, text))
        lint = [item for item in style_violations(result.response, voice, template=result.response)
                if item["value"] != "unneeded_question"]
        assert lint == [], (text, result.response, lint)
