"""Executable service contract against a local Chatwoot HTTP server."""

import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sales_agent.config import seed_examples
from sales_agent.governance import PilotController
from sales_agent.storage import StateStore

SECRET = "fictional-service-webhook-secret"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def _chatwoot_server(on_post=None):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._reply({"status": "open"})

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.loads(body)
            received.append(payload)
            if on_post is not None:
                on_post(payload)
            self._reply({"id": 42})

        def _reply(self, value):
            raw = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except BrokenPipeError:
                pass

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(url):
    with urllib.request.urlopen(url, timeout=1) as response:
        return response.status, json.load(response)


def _error_json(url):
    try:
        _get(url)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)
    raise AssertionError("endpoint unexpectedly succeeded")


@contextmanager
def _service(tmp_path, chatwoot_url, *, window_seconds=0.3, transport_timeout=10):
    data_dir = tmp_path / "data"
    store = StateStore(data_dir)
    if store.get_business("azul-b2c") is None:
        seed_examples(store)
        package = store.get_business("azul-b2c")
        PilotController(store).configure(
            "azul-b2c",
            "chatwoot",
            mode="pilot",
            cohort={"all": True},
            limits={"max_deliveries": 3},
            evaluated_package_version=package["package_version"],
            evaluation_evidence={
                "status": "passed",
                "candidate_package_version": package["package_version"],
                "evaluation": {"thresholds_met": True},
            },
            authorize=True,
        )
    config = tmp_path / "service.json"
    config.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "business_id": "azul-b2c",
                        "account_id": "11",
                        "inbox_id": "13",
                        "secret": "env:FICTIONAL_SERVICE_WEBHOOK_SECRET",
                    }
                ],
                "transport": {
                    "base_url": chatwoot_url,
                    "account_id": "11",
                    "api_access_token": "env:FICTIONAL_SERVICE_API_TOKEN",
                    "timeout_seconds": transport_timeout,
                },
                "window_seconds": window_seconds,
                "poll_interval_seconds": 0.05,
            }
        ),
        encoding="utf-8",
    )
    port = _free_port()
    env = dict(os.environ)
    env["FICTIONAL_SERVICE_WEBHOOK_SECRET"] = SECRET
    env["FICTIONAL_SERVICE_API_TOKEN"] = "fictional-api-token"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "sales_agent.cli",
            "--data-dir",
            str(data_dir),
            "serve",
            "--config",
            str(config),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f"service exited early: {process.stderr.read()}")
            try:
                _get(base_url + "/healthz")
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.05)
        else:
            raise AssertionError("service did not become healthy")
        yield base_url, process, store
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
        process.stderr.close()


def _signed_buyer_message():
    raw = json.dumps(
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
    timestamp = str(int(time.time()))
    signature = hmac.new(SECRET.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, timestamp, "sha256=" + signature


def test_serve_ack_precedes_model_and_chatwoot_delivery(tmp_path):
    with _chatwoot_server() as (chatwoot_url, received):
        with _service(tmp_path, chatwoot_url) as (base_url, _, _):
            raw, timestamp, signature = _signed_buyer_message()
            request = urllib.request.Request(
                base_url + "/webhook",
                data=raw,
                headers={"X-Chatwoot-Timestamp": timestamp, "X-Chatwoot-Signature": signature},
            )
            started = time.monotonic()
            with urllib.request.urlopen(request, timeout=2) as response:
                assert response.status == 200
                assert json.load(response)["accepted"] is True
            assert time.monotonic() - started < 0.2
            assert received == []

            deadline = time.monotonic() + 5
            while not received and time.monotonic() < deadline:
                time.sleep(0.05)
            assert len(received) == 1
            assert "camiseta" in received[0]["content"].casefold()


def test_readyz_reflects_interruption_and_storage_integrity_but_healthz_stays_live(tmp_path):
    with _chatwoot_server() as (chatwoot_url, _):
        with _service(tmp_path / "interrupted", chatwoot_url) as (base_url, _, store):
            assert _get(base_url + "/readyz") == (200, {"ready": True, "reason": "ready"})
            PilotController(store).interrupt("azul-b2c", "chatwoot")
            assert _error_json(base_url + "/readyz") == (
                503,
                {"ready": False, "reason": "channel_interrupted"},
            )
            assert _get(base_url + "/healthz") == (200, {"alive": True})

        with _service(tmp_path / "integrity", chatwoot_url) as (base_url, _, store):
            with store.connect() as db:
                db.execute("PRAGMA foreign_keys = OFF")
                db.execute(
                    "INSERT INTO business_versions(business_id, version, payload, created_at) VALUES (?, ?, ?, ?)",
                    ("orphan-fictitious", 1, "{}", "2026-09-28T00:00:00+00:00"),
                )
            assert _error_json(base_url + "/readyz") == (
                503,
                {"ready": False, "reason": "storage_integrity_failed"},
            )
            assert _get(base_url + "/healthz") == (200, {"alive": True})


def test_sigterm_during_provider_post_never_replays_after_restart(tmp_path):
    post_seen = threading.Event()
    release_post = threading.Event()

    def hold_response(_):
        post_seen.set()
        release_post.wait(timeout=3)

    with _chatwoot_server(hold_response) as (chatwoot_url, received):
        try:
            with _service(tmp_path, chatwoot_url, window_seconds=0, transport_timeout=0.2) as (
                base_url,
                process,
                store,
            ):
                raw, timestamp, signature = _signed_buyer_message()
                request = urllib.request.Request(
                    base_url + "/webhook",
                    data=raw,
                    headers={"X-Chatwoot-Timestamp": timestamp, "X-Chatwoot-Signature": signature},
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    assert response.status == 200
                assert post_seen.wait(timeout=3)
                process.terminate()
                process.wait(timeout=5)
                assert len(received) == 1

            with _service(tmp_path, chatwoot_url, window_seconds=0, transport_timeout=0.2):
                assert len(received) == 1
                assert store.list_outbox(status="unknown") or store.list_outbox(status="sent")
        finally:
            release_post.set()


def test_serve_rejects_literal_secrets_and_second_process(tmp_path):
    with _chatwoot_server() as (chatwoot_url, _):
        with _service(tmp_path, chatwoot_url) as (base_url, _, store):
            config = tmp_path / "service.json"
            document = json.loads(config.read_text(encoding="utf-8"))
            document["bindings"][0]["secret"] = "literal-secret"
            invalid = tmp_path / "invalid.json"
            invalid.write_text(json.dumps(document), encoding="utf-8")
            env = dict(os.environ)
            env["FICTIONAL_SERVICE_WEBHOOK_SECRET"] = SECRET
            env["FICTIONAL_SERVICE_API_TOKEN"] = "fictional-api-token"
            base_command = [sys.executable, "-m", "sales_agent.cli", "--data-dir", str(store.data_dir), "serve"]
            rejected = subprocess.run(
                [*base_command, "--config", str(invalid), "--port", str(_free_port())],
                env=env,
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert rejected.returncode == 2
            assert "env:NOME" in rejected.stderr

            duplicate = subprocess.run(
                [*base_command, "--config", str(config), "--port", str(_free_port())],
                env=env,
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert duplicate.returncode == 2
            assert "já existe um serviço" in duplicate.stderr
            assert _get(base_url + "/healthz") == (200, {"alive": True})
