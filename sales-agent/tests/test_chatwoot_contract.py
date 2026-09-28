"""Chatwoot webhook authentication at the public receiver boundary."""

import hashlib
import hmac
import io
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sales_agent.channel import ChatwootBinding, ChatwootChannelService, ChatwootReceiver, HTTPChatwootTransport
from sales_agent.cli import main
from sales_agent.clock import FixedClock
from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.delivery import DeliveryProcessor
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


def _outgoing_body(message_id, content):
    payload = json.loads(_body(message_id))
    payload["message"]["message_type"] = "outgoing"
    payload["message"]["content"] = content
    payload["message"]["sender"] = {"id": 91, "type": "user"}
    return json.dumps(payload, separators=(",", ":")).encode()


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


@contextmanager
def _chatwoot_server(message_id, on_post=None):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._reply({"status": "open"})

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.loads(body)
            requests.append(payload)
            if on_post is not None:
                on_post(payload)
            self._reply({"id": message_id})

        def _reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield HTTPChatwootTransport(f"http://127.0.0.1:{server.server_port}", "11", "fictional-api-token"), requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


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


def test_own_outgoing_message_echo_does_not_pause_the_conversation(tmp_path):
    store, receiver = _receiver(tmp_path)
    service = ChatwootChannelService(receiver, SellerEngine(store), DeliveryProcessor(store))
    content = "Resposta fictícia do vendedor."
    store.enqueue_message("echo-outbound-1", "azul-b2c", "12", {"response": content, "conversation_id": "12"})

    with _chatwoot_server(42) as (transport, requests):
        outcomes = service.deliver(transport)
    assert outcomes and outcomes[0]["status"] == "sent"
    assert len(requests) == 1
    assert requests[0]["content"] == content

    echo = _outgoing_body(42, content)
    reopened = StateStore(tmp_path / "data", clock=store.clock)
    receiver_after_restart = ChatwootReceiver(reopened, [ChatwootBinding("azul-b2c", "11", "13", SECRET)])
    status, result = _wsgi(receiver_after_restart, echo, _signed(echo))

    assert status == "200 OK"
    assert result["reason"] == "self_authored"
    assert reopened.load_conversation("azul-b2c", "12", "chatwoot:14")["status"] != "human_paused"


def test_unknown_human_outgoing_message_still_pauses(tmp_path):
    store, receiver = _receiver(tmp_path)
    body = _outgoing_body(99, "Oi, sou a Carla")

    result = receiver.admit(body, _signed(body))

    assert result["reason"] == "human_message"
    assert store.load_conversation("azul-b2c", "12", "chatwoot:14")["status"] == "human_paused"


def test_echo_before_provider_ack_matches_in_flight_content(tmp_path):
    store, receiver = _receiver(tmp_path)
    service = ChatwootChannelService(receiver, SellerEngine(store), DeliveryProcessor(store))
    content = "Mensagem fictícia em envio."
    store.enqueue_message("echo-outbound-2", "azul-b2c", "12", {"response": content, "conversation_id": "12"})
    echo_results = []

    def echo_before_ack(payload):
        echo = _outgoing_body(43, payload["content"])
        echo_results.append(_wsgi(receiver, echo, _signed(echo)))

    with _chatwoot_server(43, echo_before_ack) as (transport, requests):
        outcomes = service.deliver(transport)

    assert outcomes and outcomes[0]["status"] == "sent"
    assert len(requests) == 1
    assert echo_results[0][0] == "200 OK"
    assert echo_results[0][1]["reason"] == "echo_by_content"
    assert store.load_conversation("azul-b2c", "12", "chatwoot:14")["status"] != "human_paused"


def test_content_match_expires_after_120_seconds(tmp_path):
    store, receiver = _receiver(tmp_path)
    service = ChatwootChannelService(receiver, SellerEngine(store), DeliveryProcessor(store))
    content = "Mensagem fictícia em envio."
    store.enqueue_message("echo-outbound-3", "azul-b2c", "12", {"response": content, "conversation_id": "12"})
    results = []

    def late_echo(payload):
        store.clock.advance(121)
        body = _outgoing_body(44, payload["content"])
        results.append(_wsgi(receiver, body, _signed(body, timestamp="1790000131")))

    with _chatwoot_server(44, late_echo) as (transport, requests):
        service.deliver(transport)

    assert results[0][0] == "200 OK"
    assert results[0][1]["reason"] == "human_message"
    assert store.load_conversation("azul-b2c", "12", "chatwoot:14")["status"] == "human_paused"
