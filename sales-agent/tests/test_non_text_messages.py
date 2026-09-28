"""Non-text buyer messages through authenticated Chatwoot admission."""

import hashlib
import hmac
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sales_agent.channel import ChatwootBinding, ChatwootReceiver
from sales_agent.clock import FixedClock
from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.storage import StateStore
from sales_agent.transcription import HTTPTranscriber

SECRET = "fictional-media-secret"
NOW = "2026-09-28T12:00:00+00:00"


def _admit(tmp_path, *, content, attachment, message_id=51, transcriber=None):
    clock = FixedClock(NOW)
    store = StateStore(tmp_path / "data", clock=clock)
    seed_examples(store)
    receiver = ChatwootReceiver(store, [ChatwootBinding("azul-b2c", "11", "13", SECRET)])
    body = json.dumps(
        {
            "event": "message_created",
            "account": {"id": 11},
            "conversation": {"id": 12, "inbox_id": 13},
            "message": {
                "id": message_id,
                "message_type": "incoming",
                "content": content,
                "attachments": [attachment],
                "sender": {"id": 14, "type": "contact"},
            },
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(datetime.fromisoformat(NOW).timestamp()))
    signature = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    result = receiver.admit(
        body,
        {"X-Chatwoot-Timestamp": timestamp, "X-Chatwoot-Signature": "sha256=" + signature},
    )
    return store, receiver, result, SellerEngine(store, transcriber=transcriber)


def test_audio_without_transcriber_asks_for_text_and_records_attachment(tmp_path):
    store, receiver, admitted, engine = _admit(
        tmp_path,
        content="",
        attachment={"file_type": "audio", "content_type": "audio/ogg", "file_size": 1234},
    )

    assert admitted["accepted"] is True
    results = receiver.process_due(engine, now="2026-09-28T12:00:04+00:00")
    assert len(results) == 1
    assert "texto" in results[0].response.casefold()
    assert results[0].action is None
    assert results[0].state["attachments"] == [{"type": "audio", "mime": "audio/ogg", "size": 1234}]
    assert store.list_outbox("pending")


def test_owner_can_offer_human_for_audio_without_transcriber(tmp_path):
    store, receiver, _, engine = _admit(
        tmp_path,
        content="",
        attachment={"file_type": "audio", "content_type": "audio/ogg", "file_size": 1234},
    )
    package = store.get_business("azul-b2c")
    package["non_text_policy"] = "offer_human"
    store.save_business(package)

    result = receiver.process_due(engine, now="2026-09-28T12:00:04+00:00")[0]

    assert "atendente" in result.response.casefold()
    assert result.action is None


def test_transcribed_audio_is_interpreted_but_requires_text_before_sensitive_action(tmp_path):
    class ScriptedTranscriber:
        def __init__(self):
            self.urls = []

        def transcribe(self, url):
            self.urls.append(url)
            return "quero a camiseta azul M"

    transcriber = ScriptedTranscriber()
    _, receiver, admitted, engine = _admit(
        tmp_path,
        content="",
        attachment={
            "file_type": "audio",
            "content_type": "audio/ogg",
            "file_size": 1234,
            "data_url": "https://media.example.invalid/audio-51.ogg",
        },
        transcriber=transcriber,
    )

    assert admitted["accepted"] is True
    result = receiver.process_due(engine, now="2026-09-28T12:00:04+00:00")[0]
    assert transcriber.urls == ["https://media.example.invalid/audio-51.ogg"]
    assert any(item["type"] == "transcribed" for item in result.trace)
    assert any(item["type"] == "model_proposal" and item["intent"] == "buy" for item in result.trace)
    assert result.action is None
    assert result.state["pending"]["type"] == "transcribed_confirmation"


def test_image_with_payment_caption_stays_pending_provider_verification(tmp_path):
    _, receiver, admitted, engine = _admit(
        tmp_path,
        content="segue o comprovante",
        attachment={"file_type": "image", "content_type": "image/png", "file_size": 2048},
    )

    assert admitted["accepted"] is True
    result = receiver.process_due(engine, now="2026-09-28T12:00:04+00:00")[0]
    assert result.state["attachments"] == [{"type": "image", "mime": "image/png", "size": 2048}]
    assert result.state["pending"]["type"] == "payment_verification"
    assert result.state["operation"]["payment_status"] == "pending"
    assert result.action is None
    assert "não posso marcar" in result.response.casefold()
    assert "como confirmado" in result.response.casefold()


def test_http_transcriber_sends_only_media_url_to_local_contract_server():
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append((body, self.headers.get("Authorization")))
            raw = b'{"text":"quero a camiseta M"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transcriber = HTTPTranscriber(f"http://127.0.0.1:{server.server_port}/transcribe", "fictional-token")
        assert transcriber.transcribe("https://media.example.invalid/audio.ogg") == "quero a camiseta M"
        assert captured == [({"url": "https://media.example.invalid/audio.ogg"}, "Bearer fictional-token")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
