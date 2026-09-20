import hashlib
import hmac
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sales_agent.channel import (
    ChatwootBinding,
    ChatwootDeliveryProvider,
    ChatwootReceiver,
    ChatwootTransportError,
    FakeChatwootTransport,
    HTTPChatwootTransport,
)
from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.delivery import DeliveryProcessor
from sales_agent.governance import PilotController, QualitySupervisor
from sales_agent.storage import StateStore


def _payload(message_type="incoming", *, private=False, message_id=10, text="Quanto custa a camiseta azul?"):
    return {
        "event": "message_created",
        "account": {"id": 11},
        "conversation": {"id": 12, "inbox_id": 13},
        "message": {
            "id": message_id,
            "message_type": message_type,
            "private": private,
            "content": text,
            "sender": {"id": 14, "type": "contact"},
        },
    }


def _outgoing_payload(sender_type, *, message_id=20):
    payload = _payload("outgoing", message_id=message_id, text="Mensagem externa")
    payload["message"]["sender"]["type"] = sender_type
    return payload


def _signed(payload, secret="synthetic-secret"):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Chatwoot-Signature": signature}


def test_chatwoot_admission_is_authenticated_durable_and_idempotent(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])
    raw, headers = _signed(_payload())

    admitted = receiver.admit(raw, headers, received_at="2099-01-01T00:00:00+00:00")
    replay = receiver.admit(raw, headers, received_at="2099-01-01T00:00:01+00:00")

    assert admitted["accepted"] is True
    assert admitted["ack"] is True
    assert replay["duplicate"] is True
    assert len(store.list_queued_inbound()) == 1

    outgoing_raw, outgoing_headers = _signed(_payload("outgoing", message_id=11))
    outgoing = receiver.admit(outgoing_raw, outgoing_headers)
    assert outgoing["status"] == "ignored"
    assert len(store.list_queued_inbound()) == 1


def test_chatwoot_wsgi_ack_is_after_durable_admission(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])
    raw, headers = _signed(_payload(message_id=18))
    environ = {
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
        "HTTP_X_CHATWOOT_SIGNATURE": headers["X-Chatwoot-Signature"],
    }
    captured = {}

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = response_headers

    body = b"".join(receiver.wsgi(environ, start_response))
    result = json.loads(body.decode("utf-8"))

    assert captured["status"] == "200 OK"
    assert result["ack"] is True
    assert len(store.list_queued_inbound()) == 1


def test_authenticated_chatwoot_contact_can_use_external_identity_without_verified_prefix(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])
    raw, headers = _signed(
        _payload(text="Quero comprar a camiseta azul tamanho M, uma unidade para SP.", message_id=16)
    )
    receiver.admit(raw, headers, received_at="2099-01-01T00:00:00+00:00")

    results = receiver.process_due(SellerEngine(store), now="2099-01-01T00:00:05+00:00")

    assert len(results) == 1
    assert results[0].action and results[0].action["type"] == "prepare_checkout"
    assert results[0].state["contact_id"] == "chatwoot:14"

    forged = SellerEngine(store).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "forged-chatwoot",
            "contact_id": "chatwoot:14",
            "channel": "chatwoot",
            "event_id": "forged-1",
            "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
            "channel_context": {
                "account_id": "11",
                "inbox_id": "13",
                "external_message_id": "not-admitted",
                "identity_verified": True,
            },
        }
    )
    assert forged.action is None
    assert forged.response == ""
    assert forged.state["pending"]["type"] == "channel_authentication_required"


def test_chatwoot_cannot_use_simulator_identity_prefix_to_bypass_admission(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)

    result = SellerEngine(store).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "forged-prefix",
            "contact_id": "verified:attacker",
            "channel": "chatwoot",
            "event_id": "forged-prefix-1",
            "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
        }
    )

    assert result.action is None
    assert result.response == ""
    assert result.state["pending"]["type"] == "channel_authentication_required"


def test_chatwoot_admission_cannot_be_replayed_for_another_conversation_or_contact(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])
    raw, headers = _signed(
        _payload(text="Quero comprar a camiseta azul tamanho M, uma unidade para SP.", message_id=17)
    )
    admitted = receiver.admit(raw, headers)
    context = admitted["event"]["channel_context"]

    for conversation_id, contact_id in (("another-conversation", "chatwoot:14"), ("12", "chatwoot:99")):
        forged = SellerEngine(store).handle(
            {
                "business_id": "azul-b2c",
                "conversation_id": conversation_id,
                "contact_id": contact_id,
                "channel": "chatwoot",
                "event_id": "forged-%s" % conversation_id,
                "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
                "channel_context": {**context, "identity_verified": True},
            }
        )
        assert forged.action is None
        assert forged.response == ""
        assert forged.state["pending"]["type"] == "channel_authentication_required"


def test_chatwoot_bot_events_are_ignored_but_human_events_take_over_and_resume(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])

    bot_raw, bot_headers = _signed(_outgoing_payload("agent_bot", message_id=21))
    human_raw, human_headers = _signed(_outgoing_payload("administrator", message_id=22))
    assert receiver.admit(bot_raw, bot_headers)["status"] == "ignored"
    takeover = receiver.admit(human_raw, human_headers)
    assert takeover["status"] == "human_takeover"
    assert store.load_conversation("azul-b2c", "12", "chatwoot:14")["status"] == "human_paused"

    from sales_agent.conversation import SellerEngine

    resumed = SellerEngine(store).resume(
        "azul-b2c", "12", contact_id="chatwoot:14", authority="operator", reason="retomada fictícia"
    )
    assert resumed["resumed"] is True


def test_chatwoot_urgent_handoff_bypasses_turn_debounce(tmp_path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", "synthetic-secret")])
    raw, headers = _signed(_payload(text="Quero falar com uma pessoa.", message_id=15))
    receiver.admit(raw, headers, received_at="2099-01-01T00:00:00+00:00")

    results = receiver.process_due(SellerEngine(store), now="2099-01-01T00:00:01+00:00")

    assert len(results) == 1
    assert results[0].action["type"] == "human_transfer"
    assert store.list_queued_inbound() == []


def test_http_chatwoot_transport_contract_auth_endpoints_replay_and_remote_state():
    requests = []
    remote_state = {"status": "open", "assignee": None, "team": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def _write(self, status, value):
            raw = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            requests.append((self.command, self.path, dict(self.headers), None))
            self._write(200, remote_state)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            requests.append((self.command, self.path, dict(self.headers), json.loads(body.decode("utf-8"))))
            if self.path.endswith("/assignments"):
                remote_state["team"] = "7"
                self._write(200, {"id": "assignment-1"})
            else:
                self._write(200, {"id": "message-%d" % len(requests)})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = HTTPChatwootTransport(
            "http://127.0.0.1:%d" % server.server_port,
            "11",
            "fictional-api-token",
            team_id="7",
        )
        first = transport.create_message("12", "Resposta fictícia", idempotency_key="message-key")
        replay = transport.create_message("12", "Resposta fictícia", idempotency_key="message-key")
        note = transport.create_private_note("12", "Nota fictícia", idempotency_key="note-key")
        transfer = transport.request_transfer("12", idempotency_key="transfer-key")
        state = transport.get_conversation("12")

        assert first["status"] == replay["status"] == "sent"
        assert note["kind"] == "private_note"
        assert transfer["kind"] == "transfer_requested"
        assert state["status"] == "open"
        message_calls = [item for item in requests if item[1].endswith("/messages")]
        assert len(message_calls) == 2
        assert all(
            next((value for key, value in item[2].items() if key.casefold() == "api_access_token"), None)
            == "fictional-api-token"
            for item in requests
        )
        assert message_calls[0][2]["Idempotency-Key"] == "message-key"
        assert message_calls[0][3]["private"] is False
        assert message_calls[1][3]["private"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_chatwoot_transport_timeout_is_ambiguous():
    class SlowHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_GET(self):
            time.sleep(0.1)

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = HTTPChatwootTransport("http://127.0.0.1:%d" % server.server_port, "11", "fictional-api-token", timeout=0.01)
        with pytest.raises(ChatwootTransportError) as error:
            transport.get_conversation("12")
        assert error.value.ambiguous is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_chatwoot_transport_rejects_cross_origin_redirect_before_forwarding_token():
    target_calls = []

    class TargetHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_GET(self):
            target_calls.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()
    target_url = "http://127.0.0.1:%d/redirected" % target.server_port

    class RedirectHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", target_url)
            self.end_headers()

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
    redirect_thread.start()
    try:
        transport = HTTPChatwootTransport(
            "http://127.0.0.1:%d" % redirect.server_port,
            "11",
            "fictional-api-token",
        )
        with pytest.raises(ChatwootTransportError) as error:
            transport.get_conversation("12")
        assert error.value.ambiguous is False
        assert target_calls == []
    finally:
        redirect.shutdown()
        redirect.server_close()
        redirect_thread.join(timeout=2)
        target.shutdown()
        target.server_close()
        target_thread.join(timeout=2)


def test_http_chatwoot_transport_allows_relative_same_origin_redirect():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            if self.path.endswith("/12"):
                self.send_response(302)
                self.send_header("Location", "../12-final")
                self.end_headers()
                return
            raw = json.dumps({"status": "open"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = HTTPChatwootTransport(
            "http://127.0.0.1:%d" % server.server_port,
            "11",
            "fictional-api-token",
        )
        assert transport.get_conversation("12")["status"] == "open"
        assert len(requests) == 2
        assert all(
            next((value for key, value in headers.items() if key.casefold() == "api_access_token"), None)
            == "fictional-api-token"
            for _, headers in requests
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_chatwoot_remote_nested_meta_state_blocks_delivery_after_takeover():
    class NestedStateTransport:
        def get_conversation(self, conversation_id):
            return {"meta": {"status": "open", "assignee": {"id": "human-7"}, "team_id": None}}

    from sales_agent.channel import ChatwootDeliveryProvider

    provider = ChatwootDeliveryProvider(NestedStateTransport())
    decision = provider.revalidate(
        {
            "conversation_id": "12",
            "response": "Resposta fictícia",
            "action": None,
        }
    )

    assert decision["send"] is False
    assert decision["reason"] == "remote_human_takeover"


def test_chatwoot_transfer_has_separate_channel_action_and_unknown_is_not_retried(app):
    store, engine = app
    transfer = engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "chatwoot-transfer",
            "contact_id": "chatwoot:14",
            "channel": "test",
            "event_id": "transfer-1",
            "text": "Quero falar com uma pessoa.",
        }
    )
    item = store.claim_outbox(1)[0]
    transport = FakeChatwootTransport()
    delivered = DeliveryProcessor(store).process_claimed(ChatwootDeliveryProvider(transport), item)

    assert transfer.action["type"] == "human_transfer"
    assert delivered["status"] == "sent"
    assert transport.calls[0]["kind"] == "transfer_request"

    engine.commerce.set_behavior("checkout_timeout", True)
    engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "chatwoot-unknown",
            "contact_id": "chatwoot:14",
            "channel": "test",
            "event_id": "unknown-1",
            "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
        }
    )
    unknown_item = next(item for item in store.list_outbox() if item["conversation_id"] == "chatwoot-unknown")
    assert unknown_item["status"] == "pending"
    assert store.claim_outbox(1)[0]["conversation_id"] == "chatwoot-unknown"
    unknown = DeliveryProcessor(store).process_claimed(
        ChatwootDeliveryProvider(FakeChatwootTransport(behavior="unknown")),
        store.list_outbox("processing")[0],
    )
    assert unknown["status"] == "unknown"
    assert not store.claim_outbox(1)


def test_pilot_requires_evaluation_and_interrupts_public_delivery(app):
    store, engine = app
    package_version = store.get_business("azul-b2c")["package_version"]
    pilot = PilotController(store)
    try:
        pilot.configure("azul-b2c", "test", mode="pilot", cohort={"all": True}, limits={"max_deliveries": 1})
    except ValueError as exc:
        assert "autorização" in str(exc)
    else:
        raise AssertionError("piloto sem autorização deveria falhar")
    pilot.configure(
        "azul-b2c",
        "test",
        mode="pilot",
        cohort={"all": True},
        limits={"max_deliveries": 1},
        evaluated_package_version=package_version,
        authorize=True,
    )
    engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "pilot",
            "contact_id": "chatwoot:14",
            "channel": "test",
            "event_id": "pilot-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )
    claimed = store.claim_outbox(1)[0]
    pilot.interrupt("azul-b2c", "test")
    outcome = DeliveryProcessor(store, pilot=pilot).process_claimed(FakeChatwootTransport(), claimed)
    assert outcome["status"] == "observed"


def test_supervisor_observation_keeps_original_and_selective_mode_allows_one_correction(app):
    store, _ = app
    observed = QualitySupervisor(store, mode="observation", reviewer=lambda _: {"status": "rejected", "issues": ["tone"]})
    engine = SellerEngine(store, supervisor=observed)
    result = engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )
    assert "79" in result.response
    assert store.list_supervisor_reviews()

    selective = QualitySupervisor(store, mode="selective", reviewer=lambda _: {"status": "rejected", "correction": {"response": "Resposta revisada."}})
    revised_engine = SellerEngine(store, supervisor=selective)
    revised = revised_engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-selective",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-2",
            "text": "Quanto custa a camiseta azul?",
        }
    )
    assert "79" in revised.response
    assert revised.response != "Resposta revisada."
    assert not any(item["status"] == "corrected" for item in store.list_supervisor_reviews())
    assert any(item.get("type") == "supervisor_correction_blocked" for item in revised.trace)


def test_supervisor_timeout_keeps_candidate_unchanged(app):
    store, _ = app

    def slow_reviewer(_):
        time.sleep(0.01)
        return {"status": "rejected", "correction": {"response": "Resposta tardia."}}

    supervisor = QualitySupervisor(store, mode="selective", reviewer=slow_reviewer, timeout_seconds=0.001)
    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-timeout",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-timeout-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert "79" in result.response
    assert not any(item["status"] == "corrected" for item in store.list_supervisor_reviews())
    review = store.list_supervisor_reviews()[-1]
    assert review["reviewer"]["status"] == "timeout"
    assert review["reviewer"]["timed_out"] is True


def test_supervisor_timeout_returns_without_waiting_for_reviewer(app):
    store, _ = app

    def slow_reviewer(_):
        time.sleep(0.25)
        return {"status": "accepted"}

    supervisor = QualitySupervisor(store, mode="observation", reviewer=slow_reviewer, timeout_seconds=0.01)
    started = time.perf_counter()
    SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-timeout-measured",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-timeout-measured-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15
    assert store.list_supervisor_reviews()[-1]["reviewer"]["timed_out"] is True


def test_supervisor_receives_minimized_authorized_context(app):
    store, _ = app
    captured = {}

    def reviewer(value):
        captured.update(value)
        return {"status": "accepted"}

    supervisor = QualitySupervisor(store, mode="observation", reviewer=reviewer)
    SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-context",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-context-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert captured["request"] == "Quanto custa a camiseta azul?"
    assert captured["response"]
    assert captured["package"]["version"]
    assert captured["state"]["facts"]["offer_id"] == "camiseta-azul"
    assert "content" not in captured["state"]


def test_selective_supervisor_cannot_add_unsupported_price_or_deadline(app):
    store, _ = app
    supervisor = QualitySupervisor(
        store,
        mode="selective",
        reviewer=lambda _: {
            "status": "rejected",
            "correction": {"response": "A camiseta custa R$ 999 e chega em 2 dias."},
        },
    )

    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-unsupported-claims",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-unsupported-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert "79" in result.response
    assert "999" not in result.response
    assert not any(item["status"] == "corrected" for item in store.list_supervisor_reviews())
    assert any(item.get("type") == "supervisor_correction_blocked" for item in result.trace)


def test_selective_supervisor_cannot_invert_authorized_policy_polarity(app):
    store, engine = app
    engine.knowledge.ingest(
        "azul-b2c",
        "guarantee-authorized",
        "v1",
        "A garantia da camiseta cobre defeitos de fabricação.",
        title="Garantia aprovada",
        scope="camiseta-azul",
        audience="buyer",
    )
    supervisor = QualitySupervisor(
        store,
        mode="selective",
        reviewer=lambda _: {
            "status": "rejected",
            "correction": {"response": "A garantia da camiseta não cobre defeitos de fabricação."},
        },
    )

    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-policy-contradiction",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-policy-contradiction-1",
            "text": "Qual é a garantia da camiseta?",
        }
    )

    assert "cobre defeitos" in result.response.casefold()
    assert not any(item["status"] == "corrected" for item in store.list_supervisor_reviews())
    assert any(item.get("type") == "supervisor_correction_blocked" for item in result.trace)


def test_supervisor_report_aggregates_quality_latency_cost_and_failures(app):
    store, _ = app
    supervisor = QualitySupervisor(
        store,
        mode="observation",
        reviewer=lambda _: {"status": "rejected", "issues": ["unsupported_claim"], "false_positive": False, "cost": 3},
    )
    SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-report",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-report-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    report = supervisor.report()
    assert report["summary"]["reviews"] == 1
    assert report["summary"]["reviewer_rejections"] == 1
    assert report["summary"]["cost"] == 3
    assert report["summary"]["latency_ms"] >= 0
    assert report["summary"]["issues"] == {"unsupported_claim": 1}


def test_transfer_request_is_distinct_from_channel_confirmation(app):
    from sales_agent.channel import ChatwootChannelService

    store, engine = app
    result = engine.handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "transfer-confirmation",
            "contact_id": "chatwoot:14",
            "channel": "test",
            "event_id": "transfer-confirmation-1",
            "text": "Quero falar com uma pessoa.",
        }
    )
    assert result.action["type"] == "human_transfer"
    assert "confirm" not in result.response.casefold()

    service = ChatwootChannelService.__new__(ChatwootChannelService)
    service.receiver = type("Receiver", (), {"store": store})()
    not_confirmed = service.confirm_transfer(
        "azul-b2c", "transfer-confirmation", external_transfer_id="fake-transfer-1", confirmed=False
    )
    assert not_confirmed["confirmed"] is False
    confirmed = service.confirm_transfer(
        "azul-b2c", "transfer-confirmation", external_transfer_id="fake-transfer-1", confirmed=True
    )
    assert confirmed["confirmed"] is True
    assert store.load_conversation("azul-b2c", "transfer-confirmation", "unknown")["status"] == "transferred"


def test_transfer_confirmation_requires_persisted_request(app):
    from sales_agent.channel import ChatwootChannelService

    store, _ = app
    service = ChatwootChannelService.__new__(ChatwootChannelService)
    service.receiver = type("Receiver", (), {"store": store})()
    with pytest.raises(ValueError, match="solicitação de transferência"):
        service.confirm_transfer(
            "azul-b2c", "transfer-without-request", external_transfer_id="fake-transfer-2", confirmed=True
        )


def test_pilot_inspection_exposes_validation_reversal_and_retention_plan(app):
    store, _ = app
    package_version = store.get_business("azul-b2c")["package_version"]
    pilot = PilotController(store)
    pilot.configure(
        "azul-b2c",
        "chatwoot",
        mode="pilot",
        cohort={"contacts": ["chatwoot:14"]},
        limits={"max_deliveries": 1},
        evaluated_package_version=package_version,
        authorize=True,
    )

    plan = pilot.inspect("azul-b2c", "chatwoot")["operator_plan"]
    assert plan["validation"]["required"]
    assert plan["reversal"]["command"] == "pilot interrupt"
    assert plan["retention"]["metrics"] == "structured-counters"


def test_pilot_reads_nested_provider_metrics_and_keeps_fractional_cost(app):
    store, _ = app
    package_version = store.get_business("azul-b2c")["package_version"]
    evidence = {
        "status": "passed",
        "candidate_package_version": package_version,
        "evaluation": {"thresholds_met": True},
        "model": {"name": "rules-v1"},
        "backend": {"name": "sqlite-farol-v1"},
    }
    pilot = PilotController(store)
    pilot.configure(
        "azul-b2c",
        "chatwoot",
        mode="pilot",
        cohort={"all": True},
        limits={"max_cost": 0.5, "max_deliveries": 2},
        evaluated_package_version=package_version,
        evaluation_evidence=evidence,
        authorize=True,
    )

    zero_cost = pilot.decide(
        {
            "message_key": "pilot-zero-cost",
            "business_id": "azul-b2c",
            "conversation_id": "pilot-zero-cost",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
        }
    )
    assert zero_cost["send"] is True
    pilot.record(
        {"business_id": "azul-b2c", "channel": "chatwoot"},
        {"status": "cancelled"},
        decision=zero_cost,
    )

    decision = pilot.decide(
        {
            "message_key": "pilot-cost",
            "business_id": "azul-b2c",
            "conversation_id": "pilot-cost",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
            "metrics": {"provider": {"cost": 0.6, "latency_ms": 12}},
        }
    )

    assert decision["send"] is False
    assert decision["reason"] == "cost_limit"
    metrics = store.get_pilot_metrics("azul-b2c:chatwoot")
    assert metrics.get("reserved_deliveries", 0) == 0
    assert metrics.get("reserved_cost", 0) == 0

    fractional = pilot.decide(
        {
            "message_key": "pilot-fractional",
            "business_id": "azul-b2c",
            "conversation_id": "pilot-fractional",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
            "cost": 0.25,
        }
    )
    assert fractional["send"] is True
    pilot.record(
        {"business_id": "azul-b2c", "channel": "chatwoot"},
        {"status": "cancelled"},
        decision=fractional,
    )
    metrics = store.get_pilot_metrics("azul-b2c:chatwoot")
    assert metrics["reserved_deliveries"] == 0
    assert metrics["reserved_cost"] == 0
    assert metrics["cancellations"] == 2


def test_pilot_settles_nested_actual_cost_once(app):
    store, _ = app
    package_version = store.get_business("azul-b2c")["package_version"]
    pilot = PilotController(store)
    pilot.configure(
        "azul-b2c",
        "chatwoot",
        mode="pilot",
        cohort={"all": True},
        limits={"max_cost": 0.5, "max_deliveries": 3},
        evaluated_package_version=package_version,
        evaluation_evidence={
            "status": "passed",
            "candidate_package_version": package_version,
            "evaluation": {"thresholds_met": True},
            "model": {"name": "rules-v1"},
            "backend": {"name": "sqlite-farol-v1"},
        },
        authorize=True,
    )
    item = {
        "message_key": "pilot-nested-settlement",
        "business_id": "azul-b2c",
        "conversation_id": "pilot-nested-settlement",
        "channel": "chatwoot",
        "contact_id": "chatwoot:14",
        "metrics": {"provider": {"cost": 0.25}},
    }
    decision = pilot.decide(item)
    assert decision["send"] is True
    pilot.record(item, {"status": "sent", "metrics": {"provider": {"cost": 0.25}}}, decision=decision)
    metrics = store.get_pilot_metrics("azul-b2c:chatwoot")
    assert metrics["cost"] == 0.25
    assert metrics["reserved_cost"] == 0

    next_decision = pilot.decide(
        {
            **item,
            "message_key": "pilot-nested-settlement-2",
            "metrics": {"provider": {"cost": 0.1}},
        }
    )
    assert next_decision["send"] is True


def test_observation_and_cancelled_delivery_do_not_consume_reservations(app):
    store, _ = app
    pilot = PilotController(store)
    pilot.configure("azul-b2c", "chatwoot", mode="observation", cohort={"all": True})
    decision = pilot.decide(
        {
            "message_key": "observation-1",
            "business_id": "azul-b2c",
            "conversation_id": "observation-1",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
        }
    )
    assert decision["send"] is False
    metrics = store.get_pilot_metrics("azul-b2c:chatwoot")
    assert metrics.get("reserved_deliveries", 0) == 0
    assert metrics.get("reserved_cost", 0) == 0


def test_pilot_expiration_is_enforced_before_reserving_a_delivery(app):
    store, _ = app
    package_version = store.get_business("azul-b2c")["package_version"]
    pilot = PilotController(store)
    pilot.configure(
        "azul-b2c",
        "chatwoot",
        mode="pilot",
        cohort={"all": True},
        limits={"max_deliveries": 1, "expires_at": "2000-01-01T00:00:00Z"},
        evaluated_package_version=package_version,
        evaluation_evidence={
            "status": "passed",
            "candidate_package_version": package_version,
            "evaluation": {"thresholds_met": True},
            "model": {"name": "rules-v1"},
            "backend": {"name": "sqlite-farol-v1"},
        },
        authorize=True,
    )

    decision = pilot.decide(
        {
            "message_key": "pilot-expired",
            "business_id": "azul-b2c",
            "conversation_id": "pilot-expired",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
        }
    )

    assert decision["send"] is False
    assert decision["reason"] == "pilot_period_expired"
    assert store.get_pilot_metrics("azul-b2c:chatwoot").get("reserved_deliveries", 0) == 0


def test_pilot_stops_when_package_content_changes_with_same_version(app):
    store, _ = app
    package_version = store.get_business("azul-b2c")["package_version"]
    pilot = PilotController(store)
    pilot.configure(
        "azul-b2c",
        "chatwoot",
        mode="pilot",
        cohort={"all": True},
        limits={"max_deliveries": 1},
        evaluated_package_version=package_version,
        evaluation_evidence={
            "status": "passed",
            "candidate_package_version": package_version,
            "evaluation": {"thresholds_met": True},
            "model": {"name": "rules-v1"},
            "backend": {"name": "sqlite-farol-v1"},
        },
        authorize=True,
    )
    package = store.get_business("azul-b2c")
    package["offers"][0]["price"] = 80
    store.save_business(package)

    decision = pilot.decide(
        {
            "message_key": "pilot-reused-version",
            "business_id": "azul-b2c",
            "conversation_id": "pilot-reused-version",
            "channel": "chatwoot",
            "contact_id": "chatwoot:14",
        }
    )

    assert decision["send"] is False
    assert decision["reason"] == "package_changed_since_evaluation"


def test_supervisor_quality_dimensions_and_comparison_are_reported(app):
    store, _ = app
    supervisor = QualitySupervisor(store, mode="observation", reviewer=lambda _: {"status": "accepted", "cost": 2})
    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-dimensions",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-dimensions-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    review = store.list_supervisor_reviews()[-1]
    assert set(review["quality_dimensions"]) == {"request_coverage", "repetition", "evidence_support", "tone"}
    report = supervisor.report()
    assert report["comparison"]["disable_without_migration"] is True
    assert report["comparison"]["baseline"]["cases"] == 1
    assert result.response


def test_supervisor_comparison_keeps_correction_in_original_cohort(app):
    store, _ = app
    supervisor = QualitySupervisor(
        store,
        mode="selective",
        reviewer=lambda _: {
            "status": "rejected",
            "correction": {"response": "O preço da camiseta azul é R$ 79,00."},
        },
    )
    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-comparison-correction",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-comparison-correction-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert "79" in result.response
    report = supervisor.report()
    assert report["summary"]["corrections"] == 1
    assert report["comparison"]["baseline"]["cases"] == 1
    assert report["comparison"]["supervised"]["cases"] == 1
    assert len(report["comparison"]["candidate_ids"]) == 1


def test_mandatory_supervisor_policy_blocks_when_reviewer_is_unavailable(app):
    store, _ = app

    def failing_reviewer(_):
        raise RuntimeError("fake reviewer unavailable")

    supervisor = QualitySupervisor(store, mode="selective", policy="mandatory", reviewer=failing_reviewer)
    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-mandatory",
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-mandatory-1",
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert result.response == ""
    assert result.action is None
    assert result.state["pending"]["type"] == "supervisor_review_required"
    assert result.state["history"][-1]["response"] == ""
    assert result.state["history"][-1]["action"] is None
    assert any(item["type"] == "supervisor_delivery_blocked" for item in result.trace)


@pytest.mark.parametrize("mode", ["off", "observation"])
def test_mandatory_supervisor_policy_cannot_run_without_selective_gate(app, mode):
    store, _ = app
    supervisor = QualitySupervisor(
        store,
        mode=mode,
        policy="mandatory",
        reviewer=lambda _: {"status": "accepted"},
    )

    result = SellerEngine(store, supervisor=supervisor).handle(
        {
            "business_id": "azul-b2c",
            "conversation_id": "supervisor-mandatory-%s" % mode,
            "contact_id": "verified:test",
            "channel": "test",
            "event_id": "supervisor-mandatory-%s-1" % mode,
            "text": "Quanto custa a camiseta azul?",
        }
    )

    assert result.response == ""
    assert result.action is None
    assert result.state["pending"]["reason"] == "mandatory_policy_requires_selective_mode"
    assert any(item["type"] == "supervisor_delivery_blocked" for item in result.trace)
