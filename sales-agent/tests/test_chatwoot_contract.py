"""Chatwoot webhook authentication at the public receiver boundary."""

import hashlib
import hmac
import io
import json

import pytest

from sales_agent.channel import ChatwootBinding, ChatwootReceiver
from sales_agent.cli import main
from sales_agent.clock import FixedClock
from sales_agent.config import seed_examples
from sales_agent.storage import StateStore

SECRET = "fictional-webhook-secret"
NOW = "2026-09-21T14:13:30+00:00"


def _body(message_id=41):
    return json.dumps(
        {
            "event": "message_created",
            "account": {"id": 11},
            "conversation": {"id": 12, "inbox_id": 13},
            "message": {
                "id": message_id,
                "message_type": "incoming",
                "content": "Quanto custa a camiseta azul?",
                "sender": {"id": 14, "type": "contact"},
            },
        },
        separators=(",", ":"),
    ).encode()


def _signed(body, timestamp="1790000000"):
    payload = timestamp.encode() + b"." + body
    signature = hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return {
        "X-Chatwoot-Timestamp": timestamp,
        "X-Chatwoot-Signature": "sha256=" + signature,
    }


def _receiver(tmp_path):
    store = StateStore(tmp_path / "data", clock=FixedClock(NOW))
    seed_examples(store)
    binding = ChatwootBinding("azul-b2c", "11", "13", SECRET)
    return store, ChatwootReceiver(store, [binding])


def _wsgi(receiver, body, headers):
    captured = {}
    environ = {"CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    environ.update({"HTTP_" + key.upper().replace("-", "_"): value for key, value in headers.items()})
    response = b"".join(receiver.wsgi(environ, lambda status, _: captured.update(status=status)))
    return captured["status"], json.loads(response)


def test_timestamped_signed_webhook_is_admitted_once(tmp_path):
    store, receiver = _receiver(tmp_path)
    body = _body()
    headers = _signed(body)

    first = receiver.admit(body, headers)
    replay = receiver.admit(body, headers)

    assert first["accepted"] is True
    assert first["duplicate"] is False
    assert replay["duplicate"] is True
    assert len(store.list_queued_inbound()) == 1


def test_body_only_signature_requires_explicit_legacy_binding(tmp_path):
    store, receiver = _receiver(tmp_path)
    body = _body(message_id=42)
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Chatwoot-Signature": "sha256=" + signature}

    status, rejected = _wsgi(receiver, body, headers)
    assert status == "401 Unauthorized"
    assert rejected["accepted"] is False
    assert store.list_queued_inbound() == []

    legacy = ChatwootReceiver(
        store, [ChatwootBinding("azul-b2c", "11", "13", SECRET, signature_mode="legacy-body")]
    )
    status, accepted = _wsgi(legacy, body, headers)
    assert status == "200 OK"
    assert accepted["accepted"] is True
    assert legacy.diagnostics()["legacy_signature"] is True


def test_timestamp_outside_300_second_tolerance_is_rejected_before_admission(tmp_path):
    store, receiver = _receiver(tmp_path)
    body = _body(message_id=43)
    status, result = _wsgi(receiver, body, _signed(body, timestamp="1789999709"))

    assert status == "401 Unauthorized"
    assert result["accepted"] is False
    assert store.list_queued_inbound() == []

    # A rejected request leaves no replay marker that could block a later valid delivery.
    status, accepted = _wsgi(receiver, body, _signed(body))
    assert status == "200 OK"
    assert accepted["accepted"] is True
    assert len(store.list_queued_inbound()) == 1


def test_timestamped_binding_requires_prefix_and_valid_tolerance(tmp_path):
    store, receiver = _receiver(tmp_path)
    body = _body(message_id=44)
    headers = _signed(body)
    headers["X-Chatwoot-Signature"] = headers["X-Chatwoot-Signature"].removeprefix("sha256=")
    status, _ = _wsgi(receiver, body, headers)
    assert status == "401 Unauthorized"
    status, _ = _wsgi(receiver, body, _signed(body, timestamp="9" * 100))
    assert status == "401 Unauthorized"
    assert store.list_queued_inbound() == []

    for tolerance in (59, 901):
        with pytest.raises(ValueError, match="tolerância"):
            ChatwootBinding("azul-b2c", "11", "13", SECRET, timestamp_tolerance_seconds=tolerance)


def test_doctor_marks_explicit_legacy_signature_without_exposing_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FICTIONAL_CHATWOOT_SECRET", SECRET)
    binding_file = tmp_path / "binding.json"
    binding_file.write_text(
        json.dumps(
            {
                "business_id": "azul-b2c",
                "account_id": "11",
                "inbox_id": "13",
                "secret": "env:FICTIONAL_CHATWOOT_SECRET",
                "signature_mode": "legacy-body",
            }
        ),
        encoding="utf-8",
    )

    code = main(["--data-dir", str(tmp_path / "data"), "doctor", "--chatwoot-binding", str(binding_file)])
    output = capsys.readouterr().out

    assert code == 0
    assert json.loads(output)["chatwoot"]["legacy_signature"] is True
    assert SECRET not in output
