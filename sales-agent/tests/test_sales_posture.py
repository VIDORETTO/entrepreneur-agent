"""Sales posture: owner-chosen initiative, bounded by the buyer's state."""

from copy import deepcopy

import pytest

from sales_agent.config import ConfigurationManager, example_package, seed_package
from sales_agent.conversation import SellerEngine
from sales_agent.posture import initiative_from_answer
from sales_agent.storage import StateStore
from sales_agent.validation import PackageError, validate_package

from .conftest import event
from .test_grounded_drafting import ScriptedDrafter

MEIA = {"id": "meia-azul", "name": "Meia Azul", "aliases": ["meia azul"], "kind": "physical", "mode": "direct",
        "buyer_types": ["B2C"], "price_type": "fixed", "price": 19.0, "currency": "BRL",
        "required_fields": ["variant", "quantity", "region"], "stock": {"M": 5}}


def _package(initiative="suggest", **posture):
    package = deepcopy(example_package("physical"))
    package["offers"].append(deepcopy(MEIA))
    package["sales_posture"] = {
        "initiative": initiative,
        "cross_sell": [{"when_offer": "camiseta-azul", "suggest": "meia-azul"}],
        **posture,
    }
    return package


def _engine(tmp_path, package):
    store = StateStore(tmp_path)
    seed_package(store, package)
    return store, SellerEngine(store)


def _talk(engine, conversation, *texts):
    return [engine.handle(event("azul-b2c", conversation, "e%d" % index, text)) for index, text in enumerate(texts, 1)]


def _moves(result):
    return [item for item in result.trace if item["type"] == "posture_move"]


def test_default_posture_only_answers(app):
    _, engine = app
    result = _talk(engine, "default", "Quanto custa a camiseta azul?")[0]
    assert result.response == "Camiseta Azul sai por R$ 79,00 a unidade. Camiseta de algodão azul, tamanhos P, M e G."
    assert not _moves(result)


def test_suggest_adds_one_approved_complement_with_package_price(tmp_path):
    _, engine = _engine(tmp_path, _package("suggest"))
    result = _talk(engine, "suggest", "Quanto custa a camiseta azul?")[0]

    assert result.response.endswith("Se quiser, também temos Meia Azul por R$ 19,00 a unidade.")
    assert _moves(result)[0]["move"] == "cross_sell"
    assert not result.action


def test_owner_pitch_replaces_generated_complement_text(tmp_path):
    package = _package("suggest")
    package["sales_posture"]["cross_sell"][0]["pitch"] = "Ela combina com a Meia Azul, quer ver?"
    _, engine = _engine(tmp_path, package)
    result = _talk(engine, "pitch", "Quanto custa a camiseta azul?")[0]
    assert result.response.endswith("Ela combina com a Meia Azul, quer ver?")


def test_budget_limits_suggestions_and_never_two_in_a_row(tmp_path):
    _, engine = _engine(tmp_path, _package("suggest", max_suggestions_per_conversation=2))
    first, second, third = _talk(engine, "budget", "Quanto custa a camiseta azul?", "Quanto custa a camiseta azul?",
                                 "Quanto custa a camiseta azul?")
    assert _moves(first) and not _moves(second) and _moves(third)
    fourth = engine.handle(event("azul-b2c", "budget", "e4", "Quanto custa a camiseta azul?"))
    fifth = engine.handle(event("azul-b2c", "budget", "e5", "Quanto custa a camiseta azul?"))
    assert not _moves(fourth) and not _moves(fifth)


def test_lead_asks_to_prepare_and_short_yes_starts_the_purchase(tmp_path):
    _, engine = _engine(tmp_path, _package("lead"))
    offer, accepted = _talk(engine, "lead", "Quanto custa a camiseta azul?", "sim, pode")

    assert offer.response.endswith("Quer que eu já prepare o seu pedido?")
    assert any(item["type"] == "posture_close_accepted" for item in accepted.trace)
    assert accepted.state["pending"]["field"] == "variant"
    assert accepted.response == "Qual tamanho você prefere: P, M ou G?"


def test_lead_decline_stops_further_moves(tmp_path):
    _, engine = _engine(tmp_path, _package("lead", max_suggestions_per_conversation=3))
    _, declined, later, checkout = _talk(
        engine, "decline", "Quanto custa a camiseta azul?", "não, só olhando", "Quanto custa a camiseta azul?",
        "Quero comprar a camiseta azul tamanho M, 1 unidade para SP.",
    )
    assert declined.response == "Tranquilo! Se mudar de ideia, é só chamar."
    assert not declined.action
    assert not _moves(later)
    assert checkout.action["type"] == "prepare_checkout" and not _moves(checkout)


def test_open_offer_to_prepare_is_valid_for_one_turn_only(tmp_path):
    _, engine = _engine(tmp_path, _package("lead"))
    _, unrelated, late_yes = _talk(engine, "one-turn", "Quanto custa a camiseta azul?",
                                   "Qual a garantia da camiseta?", "sim")
    assert not any(item["type"] == "posture_close_accepted" for item in late_yes.trace)


def test_thanks_after_offer_to_prepare_is_not_a_purchase(tmp_path):
    _, engine = _engine(tmp_path, _package("lead"))
    _, thanks = _talk(engine, "thanks", "Quanto custa a camiseta azul?", "ok, obrigado")
    assert not thanks.action
    assert thanks.state.get("pending") is None or thanks.state["pending"].get("field") != "variant"


def test_ready_buyer_gets_checkout_without_qualification_then_one_complement(tmp_path):
    _, engine = _engine(tmp_path, _package("lead"))
    result = _talk(engine, "ready", "Quero comprar a camiseta azul tamanho M, 1 unidade para SP.")[0]

    assert result.action["type"] == "prepare_checkout"
    link, complement = result.response.split("\n\n")
    assert result.action["url"] in link
    assert complement == "Se quiser, também temos Meia Azul por R$ 19,00 a unidade."


@pytest.mark.parametrize("text", ["Meu pedido não chegou.", "Vou pensar e depois te falo."])
def test_support_and_think_never_receive_moves(tmp_path, text):
    _, engine = _engine(tmp_path, _package("lead"))
    first, price = _talk(engine, "guard", text, "Quanto custa a camiseta azul?")
    assert not _moves(first) and not _moves(price)


def test_out_of_stock_complement_is_not_suggested(tmp_path):
    package = _package("suggest")
    package["offers"][1]["stock"] = {"M": 0}
    _, engine = _engine(tmp_path, package)
    assert not _moves(_talk(engine, "stock", "Quanto custa a camiseta azul?")[0])


def test_lead_without_ask_for_close_suggests_complement(tmp_path):
    _, engine = _engine(tmp_path, _package("lead", ask_for_close=False))
    result = _talk(engine, "no-ask", "Quanto custa a camiseta azul?")[0]
    assert _moves(result)[0]["move"] == "cross_sell"


def test_objection_alternative_can_be_turned_off(tmp_path):
    package = _package("answer", alternative_on_objection=False)
    package["offers"][1].update({"price": 49.0})
    package["offers"][1].pop("stock")
    _, engine = _engine(tmp_path, package)
    result = _talk(engine, "objection", "A camiseta azul está cara.")[0]
    assert "Meia Azul" not in result.response
    assert "desconto" in result.response


@pytest.mark.parametrize(
    "posture",
    [
        {"initiative": "push"},
        {"cross_sell": [{"when_offer": "camiseta-azul", "suggest": "nao-existe"}]},
        {"cross_sell": [{"when_offer": "camiseta-azul", "suggest": "camiseta-azul"}]},
        {"cross_sell": [{"when_offer": "camiseta-azul", "suggest": "meia-azul", "pitch": "x" * 201}]},
        {"max_suggestions_per_conversation": 9},
        {"ask_for_close": "sim"},
        {"outbound": True},
    ],
)
def test_invalid_posture_is_rejected(posture):
    package = _package()
    package["sales_posture"] = posture
    with pytest.raises(PackageError):
        validate_package(package)


@pytest.mark.parametrize(
    ("answer", "initiative"),
    [("A", "answer"), ("b", "suggest"), ("C, gosto de já separar", "lead"),
     ("Gosto de sugerir um complemento", "suggest"), ("Só o preço mesmo", "answer"), ("tanto faz", None)],
)
def test_interview_scenario_answers_map_to_initiative(answer, initiative):
    assert initiative_from_answer(answer) == initiative


def _interview(store, *answers):
    manager = ConfigurationManager(store)
    session = manager.start("loja-teste", template="physical", business_name="Loja Teste")
    for answer in answers:
        payload = manager.answer(session["session_id"], answer)
    return manager, session["session_id"], payload


def test_posture_question_is_optional_and_asked_last(tmp_path):
    store = StateStore(tmp_path)
    manager, session_id, payload = _interview(store, "Camiseta", "checkout", "planilha do dono", "consultar e preparar")

    assert payload["status"] == "ready"
    assert payload["questions"][payload["next_question_index"]]["id"] == "posture"
    assert "posture" not in payload["blockers"]
    package = manager.finalize(session_id)
    assert "sales_posture" not in package


def test_posture_answer_becomes_initiative_without_inventing_complements(tmp_path):
    store = StateStore(tmp_path)
    manager, session_id, payload = _interview(store, "Camiseta", "checkout", "planilha do dono", "consultar e preparar", "C")

    package = manager.finalize(session_id)
    assert package["sales_posture"] == {"initiative": "lead"}
    assert package["owner_configuration"]["posture"]["status"] == "confirmed"


def test_unmapped_posture_answer_keeps_default_and_is_visible(tmp_path):
    store = StateStore(tmp_path)
    manager, session_id, _ = _interview(store, "Camiseta", "checkout", "planilha do dono", "consultar e preparar", "tanto faz")

    package = manager.finalize(session_id)
    assert "sales_posture" not in package
    assert package["owner_configuration"]["posture"]["status"] == "unmapped"


def test_drafter_rewrites_only_the_base_answer_and_keeps_the_posture_move(tmp_path):
    package = _package("lead")
    package["draft_mode"] = "on"
    store = StateStore(tmp_path)
    seed_package(store, package)
    drafter = ScriptedDrafter("A azul sai por R$ 79,00 cada.")
    result = SellerEngine(store, model=drafter).handle(event("azul-b2c", "draft", "e1", "Quanto custa a camiseta azul?"))

    assert "prepare o seu pedido" not in drafter.calls[0][0].template
    assert result.response == "A azul sai por R$ 79,00 cada. Quer que eu já prepare o seu pedido?"
