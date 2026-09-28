"""WhatsApp free-form delivery window at the channel boundary."""

import hashlib
import hmac
import json
from datetime import datetime

import pytest

from sales_agent.channel import (
    ChatwootBinding,
    ChatwootChannelService,
    ChatwootDeliveryProvider,
    ChatwootReceiver,
    FakeChatwootTransport,
)
from sales_agent.clock import FixedClock
from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.delivery import DeliveryProcessor
from sales_agent.governance import PilotController
from sales_agent.storage import StateStore

SECRET = "fictional-window-secret"


def _channel(tmp_path, received_at):
    clock = FixedClock(received_at)
    store = StateStore(tmp_path / "data", clock=clock)
    seed_examples(store)
    receiver = ChatwootReceiver(
        store,
        [ChatwootBinding("azul-b2c", "11", "13", SECRET, channel_kind="whatsapp")],
    )
    service = ChatwootChannelService(receiver, SellerEngine(store), DeliveryProcessor(store))
    transport = FakeChatwootTransport()
    body = json.dumps(
        {
            "event": "message_created",
            "account": {"id": 11},
            "conversation": {"id": 12, "inbox_id": 13},
            "message": {
                "id": 51,
                "message_type": "incoming",
                "content": "Quanto custa a camiseta azul?",
                "sender": {"id": 14, "type": "contact"},
            },
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(datetime.fromisoformat(received_at.replace("Z", "+00:00")).timestamp()))
    signature = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    assert receiver.admit(
        body,
        {"X-Chatwoot-Timestamp": timestamp, "X-Chatwoot-Signature": "sha256=" + signature},
    )["accepted"]
    return clock, store, service, transport


@pytest.mark.parametrize(
    ("received_at", "elapsed_seconds"),
    [("2026-09-27T12:00:01+00:00", 86399), ("2026-09-27T12:00:00+00:00", 86400)],
)
def test_whatsapp_message_within_24_hours_is_sent(tmp_path, received_at, elapsed_seconds):
    clock, store, service, transport = _channel(tmp_path, received_at)
    clock.advance(elapsed_seconds)
    assert len(service.process(now=clock.now())) == 1

    outcome = service.deliver(transport)

    assert [item["status"] for item in outcome] == ["sent"]
    assert [call["kind"] for call in transport.calls] == ["public_message"]
    assert len(store.list_outbox("sent")) == 1


def test_whatsapp_delivery_without_buyer_timestamp_fails_closed(tmp_path):
    store = StateStore(tmp_path / "data", clock=FixedClock("2026-09-28T12:00:00+00:00"))
    seed_examples(store)
    store.enqueue_message(
        "missing-buyer-timestamp",
        "azul-b2c",
        "12",
        {"channel": "chatwoot", "channel_kind": "whatsapp", "response": "Resposta fictícia"},
    )
    transport = FakeChatwootTransport()

    outcome = DeliveryProcessor(store).process_once(ChatwootDeliveryProvider(transport))

    assert outcome[0]["status"] == "window_closed"
    assert not transport.calls


def test_expired_whatsapp_message_is_closed_and_notifies_attendant_once(tmp_path):
    clock, store, service, transport = _channel(tmp_path, "2026-09-27T11:59:59+00:00")
    clock.advance(86401)
    assert len(service.process(now=clock.now())) == 1

    first = service.deliver(transport)
    second = service.deliver(transport)
    third = service.deliver(transport)

    assert first[0]["status"] == "window_closed"
    assert len(store.list_outbox("window_closed")) == 1
    assert [call["kind"] for call in transport.calls] == ["private_note"]
    assert "janela de 24 h" in transport.calls[0]["content"]
    assert second[0]["status"] == "sent"
    assert third == []


def test_window_notice_reaches_attendant_in_observation_mode(tmp_path):
    clock, store, service, transport = _channel(tmp_path, "2026-09-27T11:59:59+00:00")
    clock.advance(86401)
    assert len(service.process(now=clock.now())) == 1
    service = ChatwootChannelService(
        service.receiver,
        service.engine,
        DeliveryProcessor(store, pilot=PilotController(store)),
    )

    assert service.deliver(transport)[0]["status"] == "window_closed"
    assert service.deliver(transport)[0]["status"] == "sent"
    assert [call["kind"] for call in transport.calls] == ["private_note"]


def test_follow_up_due_after_whatsapp_window_is_blocked(tmp_path):
    clock, store, service, transport = _channel(tmp_path, "2026-09-27T12:00:00+00:00")
    clock.advance(4)
    assert len(service.process(now=clock.now())) == 1
    assert service.deliver(transport)[0]["status"] == "sent"
    package = store.get_business("azul-b2c")
    package["capabilities"]["follow_up"] = {"state": "enabled", "reason": "teste fictício"}
    store.save_business(package)
    state = store.load_conversation("azul-b2c", "12", "chatwoot:14")
    state["follow_up_allowed"] = True
    state["operation"] = {"type": "none", "status": "none"}
    store.save_conversation(state)
    assert service.engine.schedule_follow_up("azul-b2c", "12", "later", "Ainda posso ajudar?")["scheduled"]

    clock.advance(172796)
    delivery = service.deliver(transport)
    result = service.engine.revalidate_follow_up("azul-b2c", "12", "later")

    assert delivery[0]["status"] == "window_closed"
    assert [call["kind"] for call in transport.calls] == ["public_message"]
    assert result["send"] is False
    assert result["reason"] == "window_closed"
