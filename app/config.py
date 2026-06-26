from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuração única para desenvolvimento, homologação e produção.

    Os valores podem vir de variáveis de ambiente ou de um arquivo ``.env``.
    Segredos nunca devem ser versionados. Em homologação/produção, injete-os pelo
    cofre de segredos da infraestrutura.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Gestão de Perfis e Permissões"
    app_version: str = "2.0.0"
    app_env: Literal["local", "test", "homologation", "production"] = "local"
    public_base_url: str = "http://127.0.0.1:8000"
    root_path: str = ""
    debug: bool = False
    enable_api_docs: bool = True
    run_migrations_on_startup: bool = True
    seed_on_startup: bool = True

    secret_key: SecretStr = SecretStr("change-me-local-only")
    session_cookie_name: str = "caed_pp_session"
    session_max_age_seconds: int = 28_800
    session_https_only: bool = False
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    csrf_cookie_name: str = "caed_pp_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    force_https: bool = False
    trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    forwarded_allow_ips: str = "127.0.0.1"

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_statement_timeout_ms: int = 30_000

    auth_mode: Literal["disabled", "local", "oidc"] = "local"
    allow_local_auth_nonlocal: bool = False
    bootstrap_admin_name: str = "Guilherme Rodrigues"
    bootstrap_admin_email: str = "guilhermeantoniooficial@gmail.com"
    bootstrap_admin_password: SecretStr = SecretStr("TroqueEstaSenha!123")
    oidc_discovery_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr = SecretStr("")
    oidc_scopes: str = "openid profile email"
    oidc_auto_provision: bool = True
    oidc_default_role: str = "Solicitante"
    oidc_group_claim: str = "groups"
    oidc_group_role_map_json: str = "{}"
    oidc_email_claim: str = "email"
    oidc_name_claim: str = "name"
    oidc_subject_claim: str = "sub"
    oidc_logout_url: str = ""

    approval_default_reviewer: str = "Marcos Costa"
    approval_default_final_approver: str = "Ana Ferreira"

    bizagi_enabled: bool = False
    bizagi_auto_sync_after_approval: bool = False
    bizagi_base_url: str = ""
    bizagi_client_id: str = ""
    bizagi_client_secret: SecretStr = SecretStr("")
    bizagi_process_id: str = ""
    bizagi_scope: str = "api"
    bizagi_payload_xpath: str = "PerfisPermissoes.PayloadJson"
    bizagi_process_code_xpath: str = "PerfisPermissoes.CodigoProcesso"
    bizagi_process_name_xpath: str = "PerfisPermissoes.NomeProcesso"
    bizagi_status_xpath: str = "PerfisPermissoes.StatusAprovacao"
    bizagi_correlation_xpath: str = "PerfisPermissoes.CorrelationId"
    bizagi_version_xpath: str = "PerfisPermissoes.Versao"
    bizagi_timeout_seconds: int = 30
    bizagi_verify_ssl: bool = True

    n8n_enabled: bool = False
    n8n_webhook_url: str = ""
    n8n_webhook_secret: SecretStr = SecretStr("")
    n8n_timeout_seconds: int = 15
    n8n_verify_ssl: bool = True
    n8n_callback_tolerance_seconds: int = 300
    n8n_allow_legacy_secret_header: bool = False

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "nao-responda@localhost"
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False

    worker_poll_seconds: float = 2.0
    worker_batch_size: int = 10
    worker_max_attempts: int = 8
    worker_backoff_base_seconds: int = 30
    worker_backoff_max_seconds: int = 3600
    worker_lock_timeout_seconds: int = 900

    log_level: str = "INFO"
    log_json: bool = False
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05
    metrics_enabled: bool = True
    metrics_bearer_token: SecretStr = SecretStr("")

    @field_validator("trusted_hosts", "allowed_origins", mode="before")
    @classmethod
    def parse_list(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if text.startswith("["):
            parsed = json.loads(text)
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in text.split(",") if part.strip()]

    @model_validator(mode="after")
    def normalize_environment_defaults(self) -> Settings:
        if self.app_env in {"homologation", "production"}:
            self.session_https_only = True
            self.force_https = True
            self.enable_api_docs = self.enable_api_docs and self.app_env == "homologation"
            self.log_json = True
        return self

    @property
    def is_local(self) -> bool:
        return self.app_env in {"local", "test"}

    @property
    def oidc_group_role_map(self) -> dict[str, str]:
        try:
            data = json.loads(self.oidc_group_role_map_json or "{}")
        except json.JSONDecodeError:
            return {}
        return {str(key): str(value) for key, value in data.items()}

    @property
    def database_is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def database_is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    def runtime_issues(self) -> list[str]:
        issues: list[str] = []

        def is_placeholder(value: str) -> bool:
            normalized = value.strip().lower()
            markers = ("injetar", "change-me", "troque", "exemplo", "client_id_", "guid_do_", "usuario:senha")
            return not normalized or any(marker in normalized for marker in markers)

        secret = self.secret_key.get_secret_value()
        if self.app_env in {"homologation", "production"}:
            if is_placeholder(secret) or len(secret) < 32:
                issues.append("SECRET_KEY deve ser aleatória, não ser placeholder e ter pelo menos 32 caracteres.")
            if not self.database_is_postgres:
                issues.append("DATABASE_URL deve apontar para PostgreSQL em homologação/produção.")
            if self.auth_mode != "oidc" and not self.allow_local_auth_nonlocal:
                issues.append("AUTH_MODE deve ser oidc em homologação/produção.")
            if "*" in self.trusted_hosts or not self.trusted_hosts:
                issues.append("TRUSTED_HOSTS deve conter apenas os hosts oficiais.")
            if not self.public_base_url.startswith("https://"):
                issues.append("PUBLIC_BASE_URL deve usar HTTPS.")
            if self.metrics_enabled and is_placeholder(self.metrics_bearer_token.get_secret_value()):
                issues.append("METRICS_BEARER_TOKEN deve ser configurado quando métricas estiverem habilitadas.")
        if self.auth_mode == "oidc":
            if not self.oidc_discovery_url:
                issues.append("OIDC_DISCOVERY_URL não informado.")
            if is_placeholder(self.oidc_client_id):
                issues.append("OIDC_CLIENT_ID não informado ou ainda é placeholder.")
            if is_placeholder(self.oidc_client_secret.get_secret_value()):
                issues.append("OIDC_CLIENT_SECRET não informado ou ainda é placeholder.")
        if self.bizagi_enabled:
            for env_name, value in {
                "BIZAGI_BASE_URL": self.bizagi_base_url,
                "BIZAGI_CLIENT_ID": self.bizagi_client_id,
                "BIZAGI_CLIENT_SECRET": self.bizagi_client_secret.get_secret_value(),
                "BIZAGI_PROCESS_ID": self.bizagi_process_id,
                "BIZAGI_PAYLOAD_XPATH": self.bizagi_payload_xpath,
            }.items():
                if is_placeholder(str(value)):
                    issues.append(f"{env_name} não informado ou ainda é placeholder.")
        if self.n8n_enabled:
            if is_placeholder(self.n8n_webhook_url):
                issues.append("N8N_WEBHOOK_URL não informado ou ainda é placeholder.")
            if is_placeholder(self.n8n_webhook_secret.get_secret_value()) or len(self.n8n_webhook_secret.get_secret_value()) < 24:
                issues.append("N8N_WEBHOOK_SECRET deve ser real e ter pelo menos 24 caracteres.")
        if self.smtp_enabled:
            if is_placeholder(self.smtp_host):
                issues.append("SMTP_HOST não informado ou ainda é placeholder.")
            if not self.smtp_from or "@" not in self.smtp_from:
                issues.append("SMTP_FROM deve conter um endereço válido.")
        return issues


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
