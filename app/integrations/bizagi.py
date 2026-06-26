from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, settings


class BizagiConfigurationError(RuntimeError):
    pass


class BizagiRequestError(RuntimeError):
    pass


@dataclass
class BizagiStartResult:
    case_id: str
    raw: dict[str, Any]


class BizagiClient:
    """Cliente OAuth2/OData do Bizagi com cache de token e correlação."""

    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self._token: str = ""
        self._token_expires_at: float = 0

    def validate_configuration(self) -> list[str]:
        values = {
            "BIZAGI_BASE_URL": self.config.bizagi_base_url,
            "BIZAGI_CLIENT_ID": self.config.bizagi_client_id,
            "BIZAGI_CLIENT_SECRET": self.config.bizagi_client_secret.get_secret_value(),
            "BIZAGI_PROCESS_ID": self.config.bizagi_process_id,
            "BIZAGI_PAYLOAD_XPATH": self.config.bizagi_payload_xpath,
        }
        return [name for name, value in values.items() if not value]

    def build_start_parameters(self, payload: dict[str, Any]) -> dict[str, Any]:
        pairs = (
            (self.config.bizagi_process_code_xpath, payload.get("code", "")),
            (self.config.bizagi_process_name_xpath, payload.get("name", "")),
            (self.config.bizagi_status_xpath, payload.get("status", "")),
            (self.config.bizagi_correlation_xpath, payload.get("correlation_id", "")),
            (self.config.bizagi_version_xpath, payload.get("version", "")),
        )
        parameters = [
            {"xpath": xpath, "value": str(value)}
            for xpath, value in pairs
            if xpath and value is not None
        ]
        parameters.append(
            {
                "xpath": self.config.bizagi_payload_xpath,
                "value": json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
            }
        )
        return {"startParameters": parameters}

    def _get_token(self, client: httpx.Client) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        response = client.post(
            f"{self.config.bizagi_base_url}/oauth2/server/token",
            auth=(self.config.bizagi_client_id, self.config.bizagi_client_secret.get_secret_value()),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": self.config.bizagi_scope},
        )
        if response.is_error:
            raise BizagiRequestError(
                f"Falha ao obter token Bizagi ({response.status_code}): {response.text[:500]}"
            )
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise BizagiRequestError("A autenticação do Bizagi não retornou access_token.")
        self._token = str(token)
        self._token_expires_at = time.time() + int(data.get("expires_in", 300))
        return self._token

    def start_case(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> BizagiStartResult:
        missing = self.validate_configuration()
        if missing:
            raise BizagiConfigurationError("Configuração Bizagi incompleta: " + ", ".join(missing))
        if not self.config.bizagi_enabled:
            raise BizagiConfigurationError("Integração Bizagi desativada por configuração.")

        with httpx.Client(
            timeout=self.config.bizagi_timeout_seconds,
            verify=self.config.bizagi_verify_ssl,
            follow_redirects=False,
        ) as client:
            token = self._get_token(client)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Correlation-ID": str(payload.get("correlation_id", "")),
            }
            if idempotency_key:
                headers["X-Idempotency-Key"] = idempotency_key
            response = client.post(
                f"{self.config.bizagi_base_url}/odata/data/processes({self.config.bizagi_process_id})/start",
                headers=headers,
                json=self.build_start_parameters(payload),
            )
            if response.is_error:
                raise BizagiRequestError(
                    f"Falha ao iniciar caso Bizagi ({response.status_code}): {response.text[:1000]}"
                )
            raw = response.json()
            case_id = str(
                raw.get("caseNumber")
                or raw.get("idCase")
                or raw.get("value")
                or raw.get("id")
                or ""
            )
            if not case_id:
                raise BizagiRequestError("Caso criado, porém a resposta não trouxe um identificador reconhecido.")
            return BizagiStartResult(case_id=case_id, raw=raw)
