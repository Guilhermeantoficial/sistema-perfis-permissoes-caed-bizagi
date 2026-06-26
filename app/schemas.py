from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

PERMISSION_CODES = (
    "VIEW",
    "REGISTER",
    "EDIT",
    "DELETE",
    "MONITOR",
    "APPROVE",
    "ADMINISTER",
)

SYSTEM_PERMISSION_CODES = (
    "process.read",
    "process.create",
    "process.edit",
    "process.submit",
    "process.approve",
    "process.reopen",
    "process.export",
    "user.manage",
    "unit.manage",
    "role.manage",
    "approval.manage",
    "settings.manage",
    "integration.read",
    "integration.execute",
    "audit.read",
    "access.request",
    "access.approve",
    "notification.read",
)


class ProcessCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=3, max_length=250)
    description: str = Field(default="", max_length=5000)
    responsible: str = Field(default="", max_length=160)
    area: str = Field(default="", max_length=160)
    source_document: str = Field(default="", max_length=255)
    actor: str = Field(default="", max_length=160, description="Ignorado quando há usuário autenticado.")


class ProfileInput(BaseModel):
    hierarchy: str = Field(min_length=2, max_length=120)
    profile_name: str = Field(min_length=2, max_length=220)
    agent_type: str = Field(default="Não se aplica", max_length=220)
    permission_summary: str = Field(default="Não se aplica", max_length=1000)
    source_reference: str = Field(default="Cadastro manual", max_length=100)
    notes: str = Field(default="", max_length=2000)
    permissions: list[str] = Field(default_factory=list)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(code.strip().upper() for code in value))
        invalid = [code for code in normalized if code not in PERMISSION_CODES]
        if invalid:
            raise ValueError(f"Permissões inválidas: {', '.join(invalid)}")
        return normalized


class MatrixUpdate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=3, max_length=250)
    description: str = Field(default="", max_length=5000)
    responsible: str = Field(default="", max_length=160)
    area: str = Field(default="", max_length=160)
    source_document: str = Field(default="", max_length=255)
    actor: str = Field(default="", max_length=160, description="Ignorado quando há usuário autenticado.")
    row_version: int | None = Field(default=None, ge=1)
    profiles: list[ProfileInput] = Field(min_length=1, max_length=200)


class ActorInput(BaseModel):
    actor: str = Field(default="", max_length=160, description="Ignorado quando há usuário autenticado.")


class DecisionInput(ActorInput):
    note: str = Field(default="", max_length=2000)


class N8nCallbackInput(BaseModel):
    process_id: int
    event: str = Field(min_length=2, max_length=100)
    status: str = Field(default="received", max_length=60)
    message: str = Field(default="", max_length=2000)
    actor: str = Field(default="n8n", max_length=160)
    external_reference: str = Field(default="", max_length=255)


class AccessRequestCreate(BaseModel):
    process_id: int | None = None
    requested_role: str = Field(default="", max_length=120)
    requested_permissions: list[str] = Field(default_factory=list, max_length=50)
    justification: str = Field(min_length=10, max_length=4000)
    expires_at: datetime | None = None

    @field_validator("requested_permissions")
    @classmethod
    def validate_system_permissions(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        invalid = [item for item in normalized if item not in SYSTEM_PERMISSION_CODES]
        if invalid:
            raise ValueError(f"Permissões de sistema inválidas: {', '.join(invalid)}")
        return normalized


class AccessDecisionInput(BaseModel):
    note: str = Field(default="", max_length=2000)
