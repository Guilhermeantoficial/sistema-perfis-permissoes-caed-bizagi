from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, settings


class N8nConfigurationError(RuntimeError):
    pass


class N8nRequestError(RuntimeError):
    pass


@dataclass
class N8nResult:
    status_code: int
    raw: dict[str, Any]


class N8nClient:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def validate_configuration(self) -> list[str]:
        missing = []
        if not self.config.n8n_webhook_url:
            missing.append("N8N_WEBHOOK_URL")
        if not self.config.n8n_webhook_secret.get_secret_value():
            missing.append("N8N_WEBHOOK_SECRET")
        return missing

    def build_event(self, event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": "caed-perfis-permissoes",
            "event": event_name,
            "version": "2.0",
            "occurred_at": int(time.time()),
            "data": payload,
        }

    def _signed_headers(self, raw_body: bytes, idempotency_key: str) -> dict[str, str]:
        timestamp = str(int(time.time()))
        secret = self.config.n8n_webhook_secret.get_secret_value().encode()
        digest = hmac.new(secret, timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-N8N-Timestamp": timestamp,
            "X-N8N-Signature": f"sha256={digest}",
            "X-Event-ID": idempotency_key,
            "X-Idempotency-Key": idempotency_key,
        }

    def send_event(self, event_name: str, payload: dict[str, Any], *, idempotency_key: str) -> N8nResult:
        missing = self.validate_configuration()
        if missing:
            raise N8nConfigurationError("Configuração n8n incompleta: " + ", ".join(missing))
        if not self.config.n8n_enabled:
            raise N8nConfigurationError("Integração n8n desativada por configuração.")
        body = self.build_event(event_name, payload)
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        try:
            with httpx.Client(
                timeout=self.config.n8n_timeout_seconds,
                verify=self.config.n8n_verify_ssl,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    self.config.n8n_webhook_url,
                    headers=self._signed_headers(raw, idempotency_key),
                    content=raw,
                )
        except httpx.HTTPError as exc:
            raise N8nRequestError(f"Falha de comunicação com n8n: {exc}") from exc
        if response.is_error:
            raise N8nRequestError(f"Webhook n8n respondeu {response.status_code}: {response.text[:800]}")
        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text[:1000]}
        return N8nResult(status_code=response.status_code, raw=data)


def verify_callback_signature(*, raw_body: bytes, timestamp: str, signature: str) -> bool:
    if not timestamp or not signature:
        return False
    try:
        age = abs(int(time.time()) - int(timestamp))
    except ValueError:
        return False
    if age > settings.n8n_callback_tolerance_seconds:
        return False
    secret = settings.n8n_webhook_secret.get_secret_value().encode()
    expected = hmac.new(secret, timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    received = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
