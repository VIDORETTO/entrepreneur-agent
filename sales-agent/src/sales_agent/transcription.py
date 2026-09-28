"""Optional audio transcription boundary; media is never fetched by the seller."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, url: str) -> str: ...


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise ValueError("redirecionamento do transcritor não permitido")


class HTTPTranscriber:
    """Send a media URL to a configured HTTPS transcription service."""

    def __init__(self, endpoint: str, token: str, *, timeout: float = 10.0):
        parsed = urllib.parse.urlsplit(endpoint)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not ((parsed.scheme == "https" or local_http) and parsed.hostname and not parsed.username and not parsed.password):
            raise ValueError("endpoint do transcritor exige HTTPS ou localhost")
        if not token or not 0 < timeout <= 120:
            raise ValueError("credencial ou timeout do transcritor inválido")
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirects())

    def transcribe(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or len(url) > 2048:
            raise ValueError("URL de mídia inválida para transcrição")
        body = json.dumps({"url": url}, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        with self._opener.open(request, timeout=self.timeout) as response:
            raw = response.read(20_001)
        if len(raw) > 20_000:
            raise ValueError("transcrição excede limite")
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("resposta de transcrição inválida")
        return result["text"]
