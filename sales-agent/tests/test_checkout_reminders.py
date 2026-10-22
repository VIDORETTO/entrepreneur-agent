"""Abandoned-checkout reminders: scheduled by posture, revalidated at send."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sales_agent.clock import FixedClock
from sales_agent.config import example_package, seed_package
from sales_agent.conversation import SellerEngine
from sales_agent.delivery import DeliveryProcessor
from sales_agent.storage import StateStore
from sales_agent.validation import PackageError, validate_package

from .conftest import event

BUY = "Quero comprar a camiseta azul tamanho M, 1 unidade para SP."
NOON_SP = "2026-09-28T15:00:00+00:00"


class Provider:
    def __init__(self):
        self.sent = []

    def send(self, payload, *, idempotency_key):
        self.sent.append(payload)
        return {"status": "sent", "provider_id": "fake-%d" % len(self.sent)}


def _package(initiative="lead", follow_up="enabled", **posture):
    package = deepcopy(example_package("physical"))
    package["sales_posture"] = {"initiative": initiative, **posture}
    package["capabilities"]["follow_up"] = {"state": follow_up, "reason": "teste de lembrete"}
    return package


def _setup(tmp_path, package, instant=NOON_SP):
    clock = FixedClock(instant)
    store = StateStore(tmp_path, clock=clock)
    seed_package(store, package)
    return store, SellerEngine(store), clock


def _reminders(store, status="pending"):
    return [item for item in store.list_outbox(status) if item.get("kind") == "checkout_reminder"]


def _deliver_due(store, clock):
    processor = DeliveryProcessor(store)
    provider = Provider()
    outcomes = []
    for item in store.claim_outbox(100, now=clock.now()):
        outcomes.append((item, processor.process_claimed(provider, item)))
    return provider, outcomes


def test_lead_schedules_two_reminders_without_link_or_price(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("lead"))
    result = engine.handle(event("azul-b2c", "rem", "e1", BUY))

    scheduled = [item for item in result.trace if item["type"] == "reminder_scheduled"]
    assert [item["available_at"] for item in scheduled] == ["2026-09-28T18:00:00+00:00", "2026-09-28T21:00:00+00:00"]
    reminders = _reminders(store)
    assert len(reminders) == 2
    assert reminders[0]["response"].startswith("Oi! Seu pedido de Camiseta Azul ficou em aberto.")
    assert all("http" not in item["response"] and "R$" not in item["response"] for item in reminders)


@pytest.mark.parametrize(("initiative", "expected"), [("answer", 0), ("suggest", 1), ("lead", 2)])
def test_reminder_count_follows_initiative(tmp_path, initiative, expected):
    store, engine, _ = _setup(tmp_path, _package(initiative))
    engine.handle(event("azul-b2c", "count", "e1", BUY))
    assert len(_reminders(store)) == expected


def test_owner_can_turn_reminders_off_and_customize_text(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("lead", abandoned_checkout_reminders=1,
                                                 reminder_texts=["E aí, ainda quer a {produto}?"]))
    engine.handle(event("azul-b2c", "custom", "e1", BUY))
    assert [item["response"] for item in _reminders(store)] == ["E aí, ainda quer a Camiseta Azul?"]

    store2, engine2, _ = _setup(tmp_path / "off", _package("lead", abandoned_checkout_reminders=0))
    engine2.handle(event("azul-b2c", "off", "e1", BUY))
    assert _reminders(store2) == []


def test_reminders_need_follow_up_capability(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("lead", follow_up="disabled"))
    result = engine.handle(event("azul-b2c", "cap", "e1", BUY))
    assert _reminders(store) == []
    assert {"type": "reminder_not_scheduled", "reason": "follow_up_capability_disabled"} in result.trace


def test_quiet_hours_move_reminder_to_the_morning_and_drop_overlaps(tmp_path):
    # 20:30 in São Paulo: +3 h lands at 23:30, so it moves to 09:00; the
    # second (02:30) would also become 09:00 and is dropped.
    store, engine, _ = _setup(tmp_path, _package("lead"), instant="2026-09-28T23:30:00+00:00")
    engine.handle(event("azul-b2c", "night", "e1", BUY))
    assert [item["available_at"] for item in _reminders(store)] == ["2026-09-29T12:00:00+00:00"]


def test_reminder_that_would_leave_the_window_is_not_scheduled(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("suggest", reminder_after_minutes=1380),
                              instant="2026-09-28T11:00:00+00:00")
    result = engine.handle(event("azul-b2c", "late", "e1", BUY))
    assert _reminders(store) == []
    assert {"type": "reminder_not_scheduled", "reason": "window_would_close"} in result.trace


def test_due_reminder_is_delivered_once(tmp_path):
    # Delivery leases are confirmed against the system clock, so the fixed
    # instant is placed in the future (always noon in São Paulo).
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)
    store, engine, clock = _setup(tmp_path, _package("suggest"), instant=future.isoformat())
    engine.handle(event("azul-b2c", "send", "e1", BUY))
    _deliver_due(store, clock)  # the checkout link itself

    clock.advance(3 * 3600)
    provider, outcomes = _deliver_due(store, clock)
    assert [outcome["status"] for _, outcome in outcomes] == ["sent"]
    assert provider.sent[0]["response"].startswith("Oi! Seu pedido de Camiseta Azul")
    clock.advance(60)
    assert _deliver_due(store, clock)[1] == []


@pytest.mark.parametrize("reply", ["Qual a garantia da camiseta?", "Não quero receber mais mensagens.", "Enviei o comprovante do Pix."])
def test_any_buyer_message_cancels_pending_reminders(tmp_path, reply):
    store, engine, _ = _setup(tmp_path, _package("lead"))
    engine.handle(event("azul-b2c", "reply", "e1", BUY))
    engine.handle(event("azul-b2c", "reply", "e2", reply))
    assert _reminders(store) == []
    assert len(_reminders(store, "cancelled")) == 2


def test_new_link_replaces_old_reminders(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("suggest"))
    engine.handle(event("azul-b2c", "again", "e1", BUY))
    first = _reminders(store)[0]["checkout_id"]
    engine.handle(event("azul-b2c", "again", "e2", "Na verdade quero tamanho G."))
    pending = _reminders(store)
    assert all(item["checkout_id"] != first for item in pending)


def _store_at(tmp_path, instant):
    return StateStore(tmp_path, clock=FixedClock(instant))


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda state: state["operation"].update({"payment_status": "pending"}), "payment_in_progress"),
        (lambda state: state.update({"responsible": "human", "status": "human_paused"}), "human_takeover"),
        (lambda state: state.update({"follow_up_allowed": False}), "buyer_declined"),
        (lambda state: state.update({"last_event_id": "outro"}), "buyer_replied"),
    ],
)
def test_reminder_is_revalidated_against_current_state(tmp_path, mutate, reason):
    store, engine, _ = _setup(tmp_path, _package("suggest"))
    engine.handle(event("azul-b2c", "state", "e1", BUY))
    state = store.load_conversation("azul-b2c", "state", "verified:test")
    mutate(state)
    store.save_conversation(state)

    later = _store_at(tmp_path, "2026-09-28T18:00:00+00:00")
    item = _reminders(later)[0]
    assert DeliveryProcessor(later).revalidate(item)["reason"] == reason


def test_reminder_is_not_sent_in_quiet_hours_or_after_the_window(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("suggest"))
    engine.handle(event("azul-b2c", "late-send", "e1", BUY))
    item = _reminders(store)[0]

    night = _store_at(tmp_path, "2026-09-29T02:00:00+00:00")  # 23:00 in São Paulo
    assert DeliveryProcessor(night).revalidate(item)["reason"] == "quiet_hours"
    next_day = _store_at(tmp_path, "2026-09-29T15:00:00+00:00")
    assert DeliveryProcessor(next_day).revalidate(item)["reason"] == "reminder_window_closed"


def test_posture_change_cancels_pending_reminder(tmp_path):
    store, engine, _ = _setup(tmp_path, _package("lead"))
    engine.handle(event("azul-b2c", "changed", "e1", BUY))
    package = store.get_business("azul-b2c")
    package["sales_posture"]["initiative"] = "answer"
    seed_package(store, package)
    later = _store_at(tmp_path, "2026-09-28T18:00:00+00:00")
    assert DeliveryProcessor(later).revalidate(_reminders(later)[0])["send"] is False


@pytest.mark.parametrize(
    "posture",
    [
        {"abandoned_checkout_reminders": 3},
        {"abandoned_checkout_reminders": 2, "reminder_after_minutes": 700},
        {"reminder_after_minutes": 5},
        {"reminder_texts": ["Finalize aqui: https://exemplo.test"]},
        {"reminder_texts": ["a", "b", "c"]},
    ],
)
def test_invalid_reminder_settings_are_rejected(posture):
    package = _package("lead", **posture)
    with pytest.raises(PackageError):
        validate_package(package)
