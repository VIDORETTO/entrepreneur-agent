"""Single-process Chatwoot service with durable admission and delivery."""

from __future__ import annotations

import json
import os
import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping
from wsgiref.simple_server import WSGIRequestHandler, make_server

from .channel import ChatwootChannelService, ChatwootReceiver, HTTPChatwootTransport
from .clock import FixedClock
from .conversation import SellerEngine
from .delivery import DeliveryProcessor
from .governance import PilotController
from .storage import StateStore
from .transcription import HTTPTranscriber


def _environment_secret(reference: object) -> str:
    value = str(reference or "")
    if not value.startswith("env:") or not value[4:].isidentifier():
        raise ValueError("segredos do serviço exigem referência env:NOME")
    secret = os.environ.get(value[4:], "")
    if not secret:
        raise ValueError("variável de segredo do serviço não configurada")
    return secret


@dataclass(frozen=True)
class ServiceConfig:
    binding: Mapping[str, Any]
    transport: Mapping[str, Any]
    transcriber: Mapping[str, Any] | None = None
    window_seconds: float = 3.0
    poll_interval_seconds: float = 1.0
    lease_seconds: int = 60

    @classmethod
    def load(cls, path: str) -> ServiceConfig:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("configuração do serviço precisa ser objeto JSON")
        bindings = document.get("bindings")
        if not isinstance(bindings, list) or len(bindings) != 1 or not isinstance(bindings[0], dict):
            raise ValueError("serviço exige exatamente um binding Chatwoot")
        binding = dict(bindings[0])
        binding["secret"] = _environment_secret(binding.get("secret"))
        transport = document.get("transport")
        if not isinstance(transport, dict):
            raise ValueError("serviço exige transporte Chatwoot")
        transport = dict(transport)
        transport["api_access_token"] = _environment_secret(transport.get("api_access_token"))
        transcriber = document.get("transcriber")
        if transcriber is not None:
            if not isinstance(transcriber, dict):
                raise ValueError("transcriber precisa ser objeto JSON")
            transcriber = dict(transcriber)
            transcriber["token"] = _environment_secret(transcriber.get("token"))
        window_seconds = float(document.get("window_seconds", 3))
        poll_interval = float(document.get("poll_interval_seconds", 1))
        lease_seconds = int(document.get("lease_seconds", 60))
        if not 0 <= window_seconds <= 30 or not 0.01 <= poll_interval <= 10 or not 1 <= lease_seconds <= 3600:
            raise ValueError("intervalos do serviço inválidos")
        return cls(binding, transport, transcriber, window_seconds, poll_interval, lease_seconds)


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class ChannelServer:
    """Orchestrate one inbox and one transport without external infrastructure."""

    def __init__(self, data_dir: str, config: ServiceConfig, *, host: str = "127.0.0.1", port: int = 8080):
        if not 0 <= port <= 65535:
            raise ValueError("porta do serviço inválida")
        fake_now = os.environ.get("VENDEDOR_FAKE_NOW")
        if fake_now and os.environ.get("VENDEDOR_TEST_MODE") != "1":
            raise ValueError("relógio de teste exige VENDEDOR_TEST_MODE=1")
        clock = FixedClock(fake_now) if fake_now else None
        self.store = StateStore(data_dir, clock=clock)
        self.config = config
        self.host = host
        self.port = port
        self.stop_event = threading.Event()
        self.admission_lock = threading.Lock()
        self.pilot = PilotController(self.store)
        self.receiver = ChatwootReceiver(self.store, [config.binding], pilot=self.pilot)
        self.binding = next(iter(self.receiver.bindings.values()))
        if self.store.get_business(self.binding.business_id) is None:
            raise ValueError("negócio do binding Chatwoot não está configurado")
        transport = config.transport
        self.transport = HTTPChatwootTransport(
            str(transport.get("base_url", "")),
            str(transport.get("account_id", "")),
            str(transport["api_access_token"]),
            timeout=float(transport.get("timeout_seconds", 10)),
            team_id=str(transport["team_id"]) if transport.get("team_id") is not None else None,
            assignee_id=str(transport["assignee_id"]) if transport.get("assignee_id") is not None else None,
        )
        if self.transport.account_id != self.binding.account_id:
            raise ValueError("conta do transporte difere do binding")
        self.service = ChatwootChannelService(
            self.receiver,
            SellerEngine(
                self.store,
                transcriber=HTTPTranscriber(
                    str(config.transcriber.get("endpoint", "")),
                    str(config.transcriber["token"]),
                    timeout=float(config.transcriber.get("timeout_seconds", 10)),
                ) if config.transcriber else None,
            ),
            DeliveryProcessor(self.store, pilot=self.pilot),
        )

    @staticmethod
    def _json_response(start_response: Any, status: str, payload: Mapping[str, Any]) -> List[bytes]:
        body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    def readiness(self) -> Dict[str, Any]:
        report = self.store.integrity_report()
        if not report["ok"]:
            return {"ready": False, "reason": "storage_integrity_failed"}
        mode = self.pilot.inspect(self.binding.business_id, "chatwoot")["config"]
        if not mode["enabled"]:
            return {"ready": False, "reason": "channel_interrupted"}
        return {"ready": True, "reason": "ready"}

    def wsgi(self, environ: Mapping[str, Any], start_response: Any):
        path = str(environ.get("PATH_INFO", ""))
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if path == "/healthz" and method == "GET":
            return self._json_response(start_response, "200 OK", {"alive": True})
        if path == "/readyz" and method == "GET":
            result = self.readiness()
            status = "200 OK" if result["ready"] else "503 Service Unavailable"
            return self._json_response(start_response, status, result)
        if path == "/webhook" and method == "POST":
            if self.stop_event.is_set():
                return self._json_response(start_response, "503 Service Unavailable", {"error": "shutting_down"})
            return self._admit_after_ack(environ, start_response)
        return self._json_response(start_response, "404 Not Found", {"error": "not_found"})

    def _admit_after_ack(self, environ: Mapping[str, Any], start_response: Any):
        # A WSGI server writes each yielded chunk before asking for the next.
        # Keep turn processing behind this lock until the ACK body is written.
        with self.admission_lock:
            for chunk in self.receiver.wsgi(environ, start_response):
                yield chunk

    def run(self) -> None:
        if os.name != "posix":
            raise RuntimeError("bloqueio exclusivo do serviço requer POSIX")
        import fcntl

        lock_path = self.store.data_dir / "service.lock"
        with lock_path.open("a+") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("já existe um serviço para este data-dir") from exc
            self.store.recover_expired_outbox(now=self.store.clock.now())
            http = make_server(self.host, self.port, self.wsgi, handler_class=_QuietHandler)
            http.timeout = 0.2
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            previous_term = signal.signal(signal.SIGTERM, lambda *_: self.stop_event.set())
            previous_int = signal.signal(signal.SIGINT, lambda *_: self.stop_event.set())
            thread.start()
            try:
                while not self.stop_event.is_set():
                    with self.admission_lock:
                        self.receiver.process_due(
                            self.service.engine,
                            now=self.store.clock.now(),
                            window_seconds=self.config.window_seconds,
                        )
                    self.service.deliver(self.transport, limit=1, lease_seconds=self.config.lease_seconds)
                    self.stop_event.wait(self.config.poll_interval_seconds)
            finally:
                http.shutdown()
                http.server_close()
                thread.join(timeout=2)
                signal.signal(signal.SIGTERM, previous_term)
                signal.signal(signal.SIGINT, previous_int)
