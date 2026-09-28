"""Chatwoot-shaped channel contracts.

The adapter deliberately stops at the boundary: it authenticates and admits
events into the local durable queue, then a separate turn/delivery worker
does the slow work.  The classes in this module do not contact a production
Chatwoot instance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple, Union

from .storage import StateStore, durable_key, utc_now
from .turns import TurnAssembler


class ChannelAuthenticationError(ValueError):
    """The webhook could not be authenticated or mapped to a business."""


class ChannelEventRejected(ValueError):
    """The webhook was authenticated but is not a buyer message."""


class ChatwootTransportError(RuntimeError):
    """HTTP transport failure with an explicit outcome classification."""

    def __init__(self, message: str, *, ambiguous: bool):
        self.ambiguous = ambiguous
        super().__init__(message)


def _url_origin(url: str) -> Optional[Tuple[str, str, int]]:
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme.casefold() == "https" else 80
    return parsed.scheme.casefold(), parsed.hostname.casefold(), port


def _same_url_origin(left: str, right: str) -> bool:
    left_origin = _url_origin(left)
    right_origin = _url_origin(right)
    return left_origin is not None and left_origin == right_origin


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from sending the API token to a redirect target."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _same_url_origin(newurl, self.base_url):
            raise ChatwootTransportError("redirecionamento Chatwoot inseguro", ambiguous=False)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class ChatwootBinding:
    business_id: str
    account_id: str
    inbox_id: str
    secret: str
    enabled: bool = True
    signature_mode: str = "timestamped"
    timestamp_tolerance_seconds: int = 300
    channel_kind: str = "other"

    def __post_init__(self) -> None:
        if self.signature_mode not in {"timestamped", "legacy-body"}:
            raise ValueError("modo de assinatura Chatwoot inválido")
        if not 60 <= self.timestamp_tolerance_seconds <= 900:
            raise ValueError("tolerância de timestamp Chatwoot inválida")
        if self.channel_kind not in {"whatsapp", "other"}:
            raise ValueError("tipo de canal Chatwoot inválido")


def _header(headers: Mapping[str, Any], name: str) -> str:
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return str(value)
    return ""


def _first(value: Any, *keys: str) -> Any:
    if not isinstance(value, Mapping):
        return None
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


class ChatwootReceiver:
    """Authenticate and durably admit synthetic or real-shaped Chatwoot events."""

    channel = "chatwoot"

    def __init__(
        self,
        store: StateStore,
        bindings: Union[Iterable[Union[ChatwootBinding, Mapping[str, Any]]], Mapping[str, Any]],
        *,
        pilot: Any = None,
    ):
        self.store = store
        self.pilot = pilot
        self.bindings: Dict[Tuple[str, str], ChatwootBinding] = {}
        if isinstance(bindings, Mapping):
            if "business_id" in bindings:
                binding_items: Iterable[Any] = [bindings]
            elif isinstance(bindings.get("bindings"), list):
                binding_items = bindings["bindings"]
            else:
                binding_items = [dict(value, business_id=key) for key, value in bindings.items() if isinstance(value, Mapping)]
        else:
            binding_items = bindings
        for item in binding_items:
            binding = item if isinstance(item, ChatwootBinding) else self._binding_from_mapping(item)
            if not binding.enabled:
                continue
            if not binding.secret or len(binding.secret) > 4096:
                raise ValueError("segredo do binding Chatwoot inválido")
            self.bindings[(binding.account_id, binding.inbox_id)] = binding

    def diagnostics(self) -> Dict[str, Any]:
        """Report webhook contract risks without exposing binding secrets."""

        return {
            "legacy_signature": any(binding.signature_mode == "legacy-body" for binding in self.bindings.values()),
            "bindings": len(self.bindings),
        }

    @staticmethod
    def _binding_from_mapping(item: Mapping[str, Any]) -> ChatwootBinding:
        required = ("business_id", "account_id", "inbox_id", "secret")
        if any(not str(item.get(key, "")).strip() for key in required):
            raise ValueError("binding Chatwoot exige negócio, conta, inbox e segredo")
        return ChatwootBinding(
            business_id=str(item["business_id"]),
            account_id=str(item["account_id"]),
            inbox_id=str(item["inbox_id"]),
            secret=str(item["secret"]),
            enabled=bool(item.get("enabled", True)),
            signature_mode=str(item.get("signature_mode", "timestamped")),
            timestamp_tolerance_seconds=int(item.get("timestamp_tolerance_seconds", 300)),
            channel_kind=str(item.get("channel_kind", "other")),
        )

    @staticmethod
    def _raw_body(body: Union[bytes, str, Mapping[str, Any]]) -> bytes:
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode("utf-8")
        return json.dumps(dict(body), ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _payload(raw_body: Union[bytes, str, Mapping[str, Any]]) -> Dict[str, Any]:
        if isinstance(raw_body, Mapping):
            value = dict(raw_body)
        else:
            value = json.loads(ChatwootReceiver._raw_body(raw_body).decode("utf-8"))
        if not isinstance(value, dict):
            raise ChannelEventRejected("payload Chatwoot precisa ser objeto")
        return value

    @staticmethod
    def _signature_matches(binding: ChatwootBinding, raw: bytes, signature: str, timestamp: str, now: str) -> bool:
        if not signature.strip():
            return False
        if binding.signature_mode == "timestamped":
            if not (1 <= len(timestamp) <= 20 and timestamp.isascii() and timestamp.isdecimal()) or not signature.startswith(
                "sha256="
            ):
                return False
            try:
                current = datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return False
            if abs(current - int(timestamp)) > binding.timestamp_tolerance_seconds:
                return False
            payload = timestamp.encode("ascii") + b"." + raw
            supplied = signature[7:]
        else:
            payload = raw
            supplied = signature.removeprefix("sha256=").strip()
        expected = hmac.new(binding.secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, supplied)

    @staticmethod
    def _ids(payload: Mapping[str, Any]) -> Tuple[str, str, str]:
        account = _first(payload, "account_id")
        account_obj = payload.get("account")
        if account is None:
            account = _first(account_obj, "id")
        conversation = payload.get("conversation")
        inbox = _first(payload, "inbox_id")
        if inbox is None:
            inbox = _first(conversation, "inbox_id")
        if inbox is None:
            inbox = _first(payload.get("inbox"), "id")
        conversation_id = _first(payload, "conversation_id")
        if conversation_id is None:
            conversation_id = _first(conversation, "id")
        values = (account, inbox, conversation_id)
        if any(value is None or not str(value).strip() for value in values):
            raise ChannelEventRejected("evento Chatwoot sem conta, inbox ou conversa")
        return tuple(str(value) for value in values)  # type: ignore[return-value]

    def _authenticate(self, raw: bytes, payload: Mapping[str, Any], headers: Mapping[str, Any]) -> ChatwootBinding:
        account_id, inbox_id, _ = self._ids(payload)
        binding = self.bindings.get((account_id, inbox_id))
        if binding is None:
            raise ChannelAuthenticationError("conta/inbox Chatwoot não autorizado")
        signature = _header(headers, "X-Chatwoot-Signature") or _header(headers, "X-Chatwoot-Webhook-Signature")
        timestamp = _header(headers, "X-Chatwoot-Timestamp")
        if not self._signature_matches(binding, raw, signature, timestamp, self.store.clock.now()):
            raise ChannelAuthenticationError("assinatura Chatwoot inválida")
        return binding

    @staticmethod
    def _message(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        value = payload.get("message")
        return value if isinstance(value, Mapping) else payload

    @classmethod
    def _event_kind(cls, payload: Mapping[str, Any], message: Mapping[str, Any]) -> str:
        event = str(payload.get("event", "message_created")).casefold()
        if event not in {"message_created", "message.created", "message"}:
            return "ignored_event"
        message_type = message.get("message_type")
        sender = message.get("sender")
        sender_type = str(_first(sender, "type", "sender_type") or message.get("sender_type", "")).casefold()
        outgoing = message_type in {1, "1", "outgoing", "outbound"} or sender_type in {"user", "agent", "agent_bot", "administrator"}
        private = bool(message.get("private") or payload.get("private"))
        if outgoing:
            if sender_type in {"bot", "agent_bot"}:
                return "self_authored"
            if sender_type in {"agent", "user", "administrator", "human"}:
                return "human_message"
            # An outgoing event without an identity is not safe to feed back
            # into the seller; it is audited as self-authored/unknown.
            return "self_authored"
        if private:
            return "private_message"
        if message_type in {"incoming", "inbound", 0, "0", None}:
            return "buyer_message"
        return "ignored_message"

    def admit(
        self,
        body: Union[bytes, str, Mapping[str, Any]],
        headers: Optional[Mapping[str, Any]] = None,
        *,
        received_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = self._raw_body(body)
        payload = self._payload(body)
        headers = headers or {}
        binding = self._authenticate(raw, payload, headers)
        if self.store.get_business(binding.business_id) is None:
            raise ChannelAuthenticationError("negócio do binding Chatwoot não está configurado")
        account_id, inbox_id, conversation_id = self._ids(payload)
        message = self._message(payload)
        external_id = _first(message, "id") or _first(payload, "id")
        if external_id is None or not str(external_id).strip():
            raise ChannelEventRejected("evento Chatwoot sem id de mensagem")
        external_id = str(external_id)
        kind = self._event_kind(payload, message)
        echo_reason = ""
        if kind == "human_message":
            content = _first(message, "content", "text") or ""
            match = self.store.match_outbound(binding.business_id, conversation_id, external_id, str(content))
            if match:
                kind = "self_authored"
                echo_reason = "echo_by_content" if match == "content" else "self_authored"
        audit_payload = {
            "event": payload.get("event", "message_created"),
            "account_id": account_id,
            "inbox_id": inbox_id,
            "conversation_id": conversation_id,
            "message_id": external_id,
            "kind": kind,
        }
        delivery_id = _header(headers, "X-Chatwoot-Delivery")
        if delivery_id:
            audit_payload["delivery_id"] = delivery_id[:200]
        # Authenticated replays return an ACK without re-entering the queue.
        existing = self.store.get_channel_event(self.channel, self._external_key(account_id, inbox_id, external_id))
        if existing:
            return {
                "accepted": existing["status"] == "admitted",
                "duplicate": True,
                "ack": True,
                "status": existing["status"],
                "reason": existing.get("reason") or "replay",
                "event": existing.get("payload"),
            }
        if kind == "human_message":
            state = self.store.pause_conversation_for_human(
                binding.business_id,
                conversation_id,
                "chatwoot:%s" % str(_first(message.get("sender"), "id") or "human"),
                reason="human Chatwoot message",
            )
            self.store.record_channel_event(
                self.channel,
                self._external_key(account_id, inbox_id, external_id),
                audit_payload,
                status="human_takeover",
                reason="human_message",
                business_id=binding.business_id,
                conversation_id=conversation_id,
            )
            result = {
                "accepted": False,
                "duplicate": False,
                "ack": True,
                "status": "human_takeover",
                "reason": "human_message",
                "state_version": state.get("version"),
            }
            if self.pilot is not None:
                self.pilot.record_inbound(
                    {"business_id": binding.business_id, "channel": self.channel, "conversation_id": conversation_id},
                    accepted=False,
                    reason="human_message",
                )
            return result
        if kind != "buyer_message":
            self.store.record_channel_event(
                self.channel,
                self._external_key(account_id, inbox_id, external_id),
                audit_payload,
                status="ignored",
                reason=echo_reason or kind,
                business_id=binding.business_id,
                conversation_id=conversation_id,
            )
            result = {"accepted": False, "duplicate": False, "ack": True, "status": "ignored", "reason": echo_reason or kind}
            if self.pilot is not None:
                self.pilot.record_inbound(
                    {"business_id": binding.business_id, "channel": self.channel, "conversation_id": conversation_id},
                    accepted=False,
                    reason=kind,
                )
            return result
        text = _first(message, "content", "text") or _first(payload, "content", "text")
        sender = message.get("sender") if isinstance(message.get("sender"), Mapping) else payload.get("sender")
        contact = _first(sender, "id", "identifier", "email")
        if text is None or not str(text).strip() or contact is None or not str(contact).strip():
            raise ChannelEventRejected("mensagem Chatwoot sem texto ou contato")
        if len(str(text)) > 20_000 or any(len(value) > 200 for value in (conversation_id, external_id, str(contact))):
            raise ChannelEventRejected("evento Chatwoot excede o limite de tamanho")
        event_id = "chatwoot:%s" % self._external_key(account_id, inbox_id, external_id)
        if len(event_id) > 200 or len(binding.business_id) > 200:
            raise ChannelEventRejected("identidade Chatwoot excede o limite")
        contact_id = "chatwoot:%s" % str(contact)
        event = {
            "business_id": binding.business_id,
            "conversation_id": conversation_id,
            "contact_id": contact_id,
            "channel": self.channel,
            "event_id": event_id,
            "text": str(text),
            "channel_context": {
                "account_id": account_id,
                "inbox_id": inbox_id,
                "channel_kind": binding.channel_kind,
                "external_message_id": external_id,
                "identity_verified": True,
            },
        }
        # The inbound row is the ACK boundary. No model or provider call is
        # made before this insert succeeds.
        inserted = self.store.save_inbound_message(event, received_at or self.store.clock.now())
        self.store.record_channel_event(
            self.channel,
            self._external_key(account_id, inbox_id, external_id),
            {**audit_payload, "business_id": binding.business_id, "contact_id": contact_id},
            status="admitted" if inserted else "duplicate",
            reason="" if inserted else "inbound replay",
            business_id=binding.business_id,
            conversation_id=conversation_id,
        )
        if self.pilot is not None:
            self.pilot.record_inbound(event, accepted=True, reason="admitted" if inserted else "duplicate")
        return {
            "accepted": True,
            "duplicate": not inserted,
            "ack": True,
            "status": "admitted" if inserted else "duplicate",
            "event": event,
        }

    @staticmethod
    def _external_key(account_id: str, inbox_id: str, message_id: str) -> str:
        return ":".join((account_id, inbox_id, message_id))

    def process_due(self, engine: Any, *, now: Optional[str] = None, window_seconds: int = 3, max_wait_seconds: int = 15) -> List[Any]:
        assembler = TurnAssembler(self.store, engine, window_seconds=window_seconds, max_wait_seconds=max_wait_seconds)
        return assembler.process_due(now=now)

    def wsgi(self, environ: Mapping[str, Any], start_response: Any) -> List[bytes]:
        """Minimal WSGI contract useful for a local contract server."""

        length = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ.get("wsgi.input").read(length) if environ.get("wsgi.input") is not None else b""
        headers = {key[5:].replace("_", "-"): value for key, value in environ.items() if key.startswith("HTTP_")}
        try:
            result = self.admit(raw, headers)
            status = "200 OK"
        except ChannelAuthenticationError as exc:
            result = {"accepted": False, "ack": False, "error": str(exc)}
            status = "401 Unauthorized"
        except (ChannelEventRejected, ValueError) as exc:
            result = {"accepted": False, "ack": False, "error": str(exc)}
            status = "422 Unprocessable Entity"
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]


class ChatwootTransport(Protocol):
    def create_message(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]: ...

    def create_private_note(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]: ...

    def request_transfer(self, conversation_id: str, *, idempotency_key: str) -> Mapping[str, Any]: ...

    def get_conversation(self, conversation_id: str) -> Mapping[str, Any]: ...


class HTTPChatwootTransport:
    """Small executable Chatwoot API adapter.

    It implements only the published endpoints needed by this runtime and is
    intentionally usable against a localhost contract server.  No webhook
    secret or buyer identity is used as an API credential.
    """

    def __init__(
        self,
        base_url: str,
        account_id: str,
        api_access_token: str,
        *,
        timeout: float = 10.0,
        max_response_bytes: int = 2_000_000,
        team_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ):
        parsed = urllib.parse.urlsplit(str(base_url).rstrip("/"))
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not ((parsed.scheme == "https" or local_http) and parsed.hostname and not parsed.username and not parsed.password):
            raise ValueError("Chatwoot base_url precisa usar HTTPS; HTTP só é aceito em localhost")
        if not str(account_id).strip() or not str(api_access_token).strip():
            raise ValueError("Chatwoot exige account_id e api_access_token")
        if timeout <= 0 or timeout > 120 or not 1024 <= max_response_bytes <= 10_000_000:
            raise ValueError("limites HTTP do Chatwoot inválidos")
        self.base_url = str(base_url).rstrip("/")
        self.account_id = str(account_id)
        self.api_access_token = str(api_access_token)
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.team_id = str(team_id) if team_id is not None else None
        self.assignee_id = str(assignee_id) if assignee_id is not None else None
        self._idempotent: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._opener = urllib.request.build_opener(_SameOriginRedirectHandler(self.base_url))

    def _endpoint(self, conversation_id: str, suffix: str = "") -> str:
        account = urllib.parse.quote(self.account_id, safe="")
        conversation = urllib.parse.quote(str(conversation_id), safe="")
        return "%s/api/v1/accounts/%s/conversations/%s%s" % (self.base_url, account, conversation, suffix)

    def _request(
        self,
        method: str,
        url: str,
        *,
        payload: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "api_access_token": self.api_access_token,
        }
        if payload is not None:
            body = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(body) > self.max_response_bytes:
                raise ValueError("payload Chatwoot excede o limite permitido")
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                final_url = response.geturl() if hasattr(response, "geturl") else url
                if not _same_url_origin(final_url, self.base_url):
                    raise ChatwootTransportError("redirecionamento Chatwoot inseguro", ambiguous=False)
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise ChatwootTransportError("resposta Chatwoot excedeu o limite", ambiguous=False)
                if not raw:
                    return {}
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ChatwootTransportError("resposta Chatwoot não é um objeto JSON", ambiguous=False)
                return value
        except urllib.error.HTTPError as exc:
            ambiguous = exc.code in {408, 409, 425, 429} or exc.code >= 500
            raise ChatwootTransportError("Chatwoot respondeu HTTP %d" % exc.code, ambiguous=ambiguous) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ChatwootTransportError("Chatwoot indisponível", ambiguous=True) from exc

    @staticmethod
    def _provider_result(value: Mapping[str, Any], *, kind: str) -> Dict[str, Any]:
        provider_id = value.get("id")
        if provider_id is None and isinstance(value.get("message"), Mapping):
            provider_id = value["message"].get("id")
        if provider_id is None and isinstance(value.get("data"), Mapping):
            provider_id = value["data"].get("id")
        if provider_id is None:
            raise ChatwootTransportError("resposta Chatwoot sem identificador externo", ambiguous=False)
        return {"status": "sent", "provider_id": str(provider_id), "kind": kind}

    def _idempotent_request(self, key: str, operation: Any) -> Dict[str, Any]:
        with self._lock:
            if key in self._idempotent:
                return dict(self._idempotent[key])
            value = dict(operation())
            self._idempotent[key] = dict(value)
            return value

    def create_message(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]:
        if not content or len(content) > 20_000:
            raise ValueError("mensagem Chatwoot vazia ou grande demais")
        payload = {"content": content, "message_type": "outgoing", "private": False, "content_type": "text"}
        return self._idempotent_request(
            idempotency_key,
            lambda: self._provider_result(
                self._request("POST", self._endpoint(conversation_id, "/messages"), payload=payload, idempotency_key=idempotency_key),
                kind="public_message",
            ),
        )

    def create_private_note(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]:
        if not content or len(content) > 20_000:
            raise ValueError("nota Chatwoot vazia ou grande demais")
        payload = {"content": content, "message_type": "outgoing", "private": True, "content_type": "text"}
        return self._idempotent_request(
            idempotency_key,
            lambda: self._provider_result(
                self._request("POST", self._endpoint(conversation_id, "/messages"), payload=payload, idempotency_key=idempotency_key),
                kind="private_note",
            ),
        )

    def request_transfer(self, conversation_id: str, *, idempotency_key: str) -> Mapping[str, Any]:
        if not self.team_id and not self.assignee_id:
            raise ChatwootTransportError("transferência Chatwoot exige team_id ou assignee_id", ambiguous=False)
        payload: Dict[str, Any] = {}
        if self.team_id:
            payload["team_id"] = self.team_id
        if self.assignee_id:
            payload["assignee_id"] = self.assignee_id
        return self._idempotent_request(
            idempotency_key,
            lambda: self._provider_result(
                self._request("POST", self._endpoint(conversation_id, "/assignments"), payload=payload, idempotency_key=idempotency_key),
                kind="transfer_requested",
            ),
        )

    def get_conversation(self, conversation_id: str) -> Mapping[str, Any]:
        return self._request("GET", self._endpoint(conversation_id))


class ChatwootDeliveryProvider:
    """Translate an outbox envelope to the three channel actions."""

    def __init__(self, transport: ChatwootTransport):
        self.transport = transport

    @staticmethod
    def prepare_send(store: StateStore, item: Mapping[str, Any]) -> bool:
        action = item.get("action") if isinstance(item.get("action"), Mapping) else {}
        if action.get("type") in {"human_transfer", "private_note", "internal_note"}:
            return True
        if bool(item.get("private")) or not item.get("response"):
            return True
        return store.begin_outbound(item)

    def send(self, payload: Mapping[str, Any], *, idempotency_key: str) -> Mapping[str, Any]:
        conversation_id = str(payload.get("conversation_id", ""))
        if not conversation_id:
            return {"status": "rejected", "error": "conversation_id ausente"}
        action = payload.get("action") if isinstance(payload.get("action"), Mapping) else {}
        action_type = str(action.get("type", ""))
        if action_type == "human_transfer":
            result = dict(self.transport.request_transfer(conversation_id, idempotency_key=idempotency_key))
            result.setdefault("kind", "transfer_requested")
            return result
        response = str(payload.get("response", ""))
        if not response:
            return {"status": "accepted", "kind": "no_public_message"}
        if action_type in {"private_note", "internal_note"} or bool(payload.get("private")):
            result = dict(self.transport.create_private_note(conversation_id, response, idempotency_key=idempotency_key))
            result.setdefault("kind", "private_note")
            return result
        result = dict(self.transport.create_message(conversation_id, response, idempotency_key=idempotency_key))
        result.setdefault("kind", "public_message")
        return result

    def revalidate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        getter = getattr(self.transport, "get_conversation", None)
        if not callable(getter):
            return {"send": True, "reason": "remote_state_not_supported_by_transport"}
        state = dict(getter(str(payload.get("conversation_id", ""))))
        remote_meta = state.get("meta") if isinstance(state.get("meta"), Mapping) else {}
        status = str(
            state.get("status")
            or state.get("conversation_status")
            or remote_meta.get("status")
            or remote_meta.get("conversation_status", "")
        ).casefold()
        action = payload.get("action") if isinstance(payload.get("action"), Mapping) else {}
        if action.get("type") != "human_transfer" and status in {"resolved", "closed", "archived"}:
            return {"send": False, "reason": "remote_conversation_closed"}
        assignee = (
            state.get("assignee")
            or state.get("assignee_id")
            or remote_meta.get("assignee")
            or remote_meta.get("assignee_id")
        )
        team = state.get("team") or state.get("team_id") or remote_meta.get("team") or remote_meta.get("team_id")
        if action.get("type") != "human_transfer" and (assignee or team):
            return {"send": False, "reason": "remote_human_takeover"}
        return {"send": True, "reason": "remote_state_allows_delivery", "remote_status": status}


class FakeChatwootTransport:
    """Contract double; each call is inspectable and contains no real IDs."""

    def __init__(self, *, behavior: str = "sent"):
        self.behavior = behavior
        self.calls: List[Dict[str, Any]] = []

    def _call(self, kind: str, conversation_id: str, content: str, idempotency_key: str) -> Mapping[str, Any]:
        self.calls.append({"kind": kind, "conversation_id": conversation_id, "content": content, "idempotency_key": idempotency_key})
        if self.behavior in {"unknown", "timeout"}:
            return {"status": "unknown", "provider_id": "fake-unknown"}
        if self.behavior == "rejected":
            return {"status": "rejected", "error": "fake rejection"}
        return {"status": "sent", "provider_id": durable_key("fake-chatwoot", idempotency_key)}

    def create_message(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]:
        return self._call("public_message", conversation_id, content, idempotency_key)

    def create_private_note(self, conversation_id: str, content: str, *, idempotency_key: str) -> Mapping[str, Any]:
        return self._call("private_note", conversation_id, content, idempotency_key)

    def request_transfer(self, conversation_id: str, *, idempotency_key: str) -> Mapping[str, Any]:
        return self._call("transfer_request", conversation_id, "", idempotency_key)


class ChatwootChannelService:
    """Compose admission, turn processing and revalidated delivery."""

    def __init__(self, receiver: ChatwootReceiver, engine: Any, delivery: Any):
        self.receiver = receiver
        self.engine = engine
        self.delivery = delivery

    def receive(
        self,
        body: Union[bytes, str, Mapping[str, Any]],
        headers: Mapping[str, Any],
        *,
        received_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.receiver.admit(body, headers, received_at=received_at)

    def process(self, *, now: Optional[str] = None) -> List[Any]:
        return self.receiver.process_due(self.engine, now=now)

    def deliver(self, transport: ChatwootTransport, *, limit: int = 10, lease_seconds: int = 60) -> List[Dict[str, Any]]:
        return self.delivery.process_once(ChatwootDeliveryProvider(transport), limit=limit, lease_seconds=lease_seconds)

    def confirm_transfer(
        self,
        business_id: str,
        conversation_id: str,
        *,
        external_transfer_id: str,
        confirmed: bool,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Persist channel confirmation separately from the request action."""

        if not external_transfer_id.strip():
            raise ValueError("transferência exige identificador externo")
        state = self.receiver.store.load_conversation(business_id, conversation_id, "unknown")
        if not state:
            raise ValueError("conversa não encontrada")
        if not self.receiver.store.has_persisted_action(business_id, conversation_id, "human_transfer"):
            raise ValueError("não existe solicitação de transferência persistida")
        expected_version = int(state.get("version", 0))
        state["transfer"] = {
            "requested": True,
            "confirmed": bool(confirmed),
            "external_transfer_id": external_transfer_id,
            "reason": reason,
            "confirmed_at": utc_now(),
        }
        if confirmed:
            state["status"] = "transferred"
            state["responsible"] = "human"
        state["version"] = expected_version + 1
        if not self.receiver.store.save_conversation_if_version(state, expected_version):
            raise ValueError("conversa mudou durante a confirmação da transferência")
        return {"business_id": business_id, "conversation_id": conversation_id, **state["transfer"]}
