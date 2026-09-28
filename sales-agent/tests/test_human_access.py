"""Human access and loop handling through the public engine."""

from copy import deepcopy

from sales_agent.clock import FixedClock
from sales_agent.config import seed_package
from sales_agent.conversation import SellerEngine
from sales_agent.storage import StateStore

from .conftest import event


def configured(tmp_path, *, instant="2026-09-28T12:00:00+00:00", hours=None):
    from sales_agent.config import example_package

    package = deepcopy(example_package("physical"))
    if hours is not None:
        package["service_hours"] = hours
    clock = FixedClock(instant)
    store = StateStore(tmp_path, clock=clock)
    seed_package(store, package)
    return store, SellerEngine(store), package, clock


def test_ac041_repeated_unrecognized_messages_offer_human(tmp_path):
    _, engine, package, _ = configured(tmp_path)
    business = package["business"]["id"]
    for number in (1, 2):
        engine.handle(event(business, "loop", f"e{number}", "blorf zyxw"))
    result = engine.handle(event(business, "loop", "e3", "blorf zyxw"))
    assert "atendente" in result.response.lower() or "pessoa" in result.response.lower()
    assert any(item["type"] == "loop_detected" for item in result.trace)


def test_ac042_after_hours_transfer_names_next_opening(tmp_path):
    hours = {"timezone": "America/Sao_Paulo", "intervals": {
        "monday": [{"start": "09:00", "end": "18:00"}],
        "tuesday": [{"start": "09:00", "end": "18:00"}],
    }}
    _, engine, package, _ = configured(tmp_path, instant="2026-09-29T02:00:00+00:00", hours=hours)
    result = engine.handle(event(package["business"]["id"], "after-hours", "e1", "Quero falar com uma pessoa"))
    assert result.action["type"] == "human_transfer"
    assert result.action["status"] == "queued"
    assert "amanhã às 9h" in result.response.lower()


def test_ac043_frustrated_buyer_transfers_with_confirmed_facts(tmp_path):
    _, engine, package, _ = configured(tmp_path)
    business = package["business"]["id"]
    engine.handle(event(business, "frustrated", "e1", "Quero camiseta azul tamanho M para SP"))
    result = engine.handle(event(business, "frustrated", "e2", "Já falei isso três vezes, quero uma pessoa"))
    assert result.action["type"] == "human_transfer"
    assert result.action["context"]["facts"]["variant"] == "M"
    assert result.action["context"]["facts"]["region"] == "SP"
    assert "?" not in result.response


def test_ac044_elapsed_week_does_not_close_conversation(tmp_path):
    store, engine, package, clock = configured(tmp_path)
    business = package["business"]["id"]
    result = engine.handle(event(business, "still-open", "e1", "Olá"))
    assert result.state["status"] == "active"
    clock.advance(7 * 24 * 3600)
    reopened = store.load_conversation(business, "still-open", "verified:test")
    assert reopened["status"] == "active"
    assert reopened["phase"] not in {"concluído", "encerrado_sem_venda", "transferido"}


def test_invalid_service_hours_are_rejected(tmp_path):
    import pytest

    from sales_agent.validation import PackageError, validate_package

    _, _, package, _ = configured(tmp_path)
    package["service_hours"] = {"timezone": "Mars/Nowhere", "intervals": {"monday": [{"start": "09:00", "end": "18:00"}]}}
    with pytest.raises(PackageError, match="service_hours"):
        validate_package(package)
