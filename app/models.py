from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid4_str() -> str:
    return str(uuid.uuid4())


class ProcessSpecification(Base):
    __tablename__ = "process_specifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=uuid4_str)
    correlation_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=uuid4_str)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    responsible: Mapped[str] = mapped_column(String(160), default="")
    area: Mapped[str] = mapped_column(String(160), default="")
    source_document: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    updated_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bizagi_case_id: Mapped[str] = mapped_column(String(120), default="")
    bizagi_sync_status: Mapped[str] = mapped_column(String(40), default="not_configured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    profiles: Mapped[list[ProfileDefinition]] = relationship(
        back_populates="process", cascade="all, delete-orphan", order_by="ProfileDefinition.sort_order"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="process", cascade="all, delete-orphan", order_by="AuditEvent.created_at"
    )
    integration_jobs: Mapped[list[IntegrationJob]] = relationship(
        back_populates="process", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list[ApprovalRequest]] = relationship(
        back_populates="process", cascade="all, delete-orphan", order_by="ApprovalRequest.created_at"
    )
    access_requests: Mapped[list[AccessRequest]] = relationship(back_populates="process")


class ProfileDefinition(Base):
    __tablename__ = "profile_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process_specifications.id", ondelete="CASCADE"), index=True)
    hierarchy: Mapped[str] = mapped_column(String(120))
    profile_name: Mapped[str] = mapped_column(String(220))
    agent_type: Mapped[str] = mapped_column(String(220), default="Não se aplica")
    permission_summary: Mapped[str] = mapped_column(Text, default="Não se aplica")
    source_reference: Mapped[str] = mapped_column(String(100), default="Documento, p. 4")
    notes: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    process: Mapped[ProcessSpecification] = relationship(back_populates="profiles")
    permissions: Mapped[list[ProfilePermission]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class ProfilePermission(Base):
    __tablename__ = "profile_permissions"
    __table_args__ = (UniqueConstraint("profile_id", "permission_code", name="uq_profile_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile_definitions.id", ondelete="CASCADE"), index=True)
    permission_code: Mapped[str] = mapped_column(String(40))

    profile: Mapped[ProfileDefinition] = relationship(back_populates="permissions")


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    role_name: Mapped[str] = mapped_column(String(120), default="Solicitante", index=True)
    unit_name: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    access_requests: Mapped[list[AccessRequest]] = relationship(
        back_populates="requester", foreign_keys="AccessRequest.requester_id"
    )
    grants: Mapped[list[UserPermissionGrant]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OrganizationalUnit(Base):
    __tablename__ = "organizational_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), unique=True)
    responsible: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoleDefinition(Base):
    __tablename__ = "role_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    permission_codes_json: Mapped[str] = mapped_column(Text, default="[]")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserPermissionGrant(Base):
    __tablename__ = "user_permission_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "process_id", "permission_code", name="uq_user_process_permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    process_id: Mapped[int | None] = mapped_column(
        ForeignKey("process_specifications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    permission_code: Mapped[str] = mapped_column(String(120), index=True)
    granted_by: Mapped[str] = mapped_column(String(255), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[UserAccount] = relationship(back_populates="grants")


class ApprovalFlowDefinition(Base):
    __tablename__ = "approval_flow_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    reviewer_name: Mapped[str] = mapped_column(String(160), default="")
    final_approver_name: Mapped[str] = mapped_column(String(160), default="")
    sla_hours: Mapped[int] = mapped_column(Integer, default=48)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    requests: Mapped[list[ApprovalRequest]] = relationship(back_populates="flow")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process_specifications.id", ondelete="CASCADE"), index=True)
    flow_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_flow_definitions.id", ondelete="SET NULL"), nullable=True
    )
    stage_order: Mapped[int] = mapped_column(Integer, default=1)
    stage_name: Mapped[str] = mapped_column(String(120), default="Revisão técnica")
    requested_by: Mapped[str] = mapped_column(String(255), default="")
    assigned_to: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    decision_by: Mapped[str] = mapped_column(String(255), default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    process: Mapped[ProcessSpecification] = relationship(back_populates="approval_requests")
    flow: Mapped[ApprovalFlowDefinition | None] = relationship(back_populates="requests")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=uuid4_str)
    requester_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    process_id: Mapped[int | None] = mapped_column(
        ForeignKey("process_specifications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_role: Mapped[str] = mapped_column(String(120), default="")
    requested_permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    justification: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    assigned_to: Mapped[str] = mapped_column(String(255), default="")
    decision_by: Mapped[str] = mapped_column(String(255), default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requester: Mapped[UserAccount] = relationship(back_populates="access_requests", foreign_keys=[requester_id])
    process: Mapped[ProcessSpecification | None] = relationship(back_populates="access_requests")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int | None] = mapped_column(
        ForeignKey("process_specifications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(60), default="business", index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(255), default="Sistema")
    actor_email: Mapped[str] = mapped_column(String(255), default="")
    request_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    process: Mapped[ProcessSpecification | None] = relationship(back_populates="audit_events")


class IntegrationJob(Base):
    __tablename__ = "integration_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int | None] = mapped_column(
        ForeignKey("process_specifications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), default="bizagi", index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    event_name: Mapped[str] = mapped_column(String(100), default="", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, default=uuid4_str)
    correlation_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=8)
    request_json: Mapped[str] = mapped_column(Text, default="{}")
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str] = mapped_column(String(120), default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    process: Mapped[ProcessSpecification | None] = relationship(back_populates="integration_jobs")


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    event_id: Mapped[str] = mapped_column(String(160), index=True)
    payload_hash: Mapped[str] = mapped_column(String(128), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient: Mapped[str] = mapped_column(String(255), default="Todos", index=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="info")
    link: Mapped[str] = mapped_column(String(500), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
