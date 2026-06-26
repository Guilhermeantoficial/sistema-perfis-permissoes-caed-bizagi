from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.authorization import DEFAULT_ROLE_PERMISSIONS
from app.config import settings
from app.models import (
    ApprovalFlowDefinition,
    ApprovalRequest,
    AppSetting,
    Notification,
    OrganizationalUnit,
    ProcessSpecification,
    RoleDefinition,
    UserAccount,
)
from app.services.outbox_service import enqueue_job


def ensure_admin_seed(db: Session) -> None:
    admin = db.scalar(select(UserAccount).where(UserAccount.email == settings.bootstrap_admin_email.lower()))
    if not admin:
        db.add(
            UserAccount(
                name=settings.bootstrap_admin_name,
                email=settings.bootstrap_admin_email.lower(),
                password_hash=(
                    hash_password(settings.bootstrap_admin_password.get_secret_value())
                    if settings.is_local and settings.auth_mode == "local"
                    else ""
                ),
                role_name="Administrador",
                unit_name="Supervisão de Planejamento e Protocolos",
            )
        )
    if settings.is_local and not db.scalar(
        select(UserAccount).where(UserAccount.email == "ana.ferreira@caed.local")
    ):
        db.add_all(
            [
                UserAccount(
                    name="Ana Ferreira",
                    email="ana.ferreira@caed.local",
                    password_hash=hash_password("Homologacao!123"),
                    role_name="Aprovador",
                    unit_name="Governança",
                ),
                UserAccount(
                    name="Marcos Costa",
                    email="marcos.costa@caed.local",
                    password_hash=hash_password("Homologacao!123"),
                    role_name="Revisor",
                    unit_name="Tecnologia da Informação",
                ),
                UserAccount(
                    name="Larissa Souza",
                    email="larissa.souza@caed.local",
                    password_hash=hash_password("Homologacao!123"),
                    role_name="Solicitante",
                    unit_name="Organização do Campo",
                ),
            ]
        )

    if not db.scalar(select(OrganizationalUnit.id).limit(1)):
        db.add_all(
            [
                OrganizationalUnit(code="SPP", name="Supervisão de Planejamento e Protocolos", responsible=settings.bootstrap_admin_name),
                OrganizationalUnit(code="TI", name="Tecnologia da Informação", responsible="Marcos Costa"),
                OrganizationalUnit(code="GOV", name="Governança", responsible="Ana Ferreira"),
                OrganizationalUnit(code="CAMPO", name="Organização do Campo", responsible="Larissa Souza"),
            ]
        )

    descriptions = {
        "Administrador": "Administra parâmetros, integrações, usuários e fluxos.",
        "Solicitante": "Cria e altera processos enquanto estão em rascunho.",
        "Revisor": "Executa a revisão técnica da matriz de permissões.",
        "Aprovador": "Realiza a aprovação final e bloqueia a versão.",
        "Auditor": "Consulta histórico, decisões e integrações sem editar.",
        "Usuário": "Consulta processos e solicita acesso adicional.",
    }
    for name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.scalar(select(RoleDefinition).where(RoleDefinition.name == name))
        if not role:
            db.add(
                RoleDefinition(
                    name=name,
                    description=descriptions.get(name, "Papel de acesso do sistema."),
                    permission_codes_json=json.dumps(sorted(permissions)),
                    is_system=True,
                )
            )

    if not db.scalar(select(ApprovalFlowDefinition.id).limit(1)):
        db.add(
            ApprovalFlowDefinition(
                name="Fluxo padrão de perfis e permissões",
                description=(
                    "Encaminha primeiro para revisão técnica e depois para aprovação final. "
                    "Os responsáveis podem ser alterados nesta página."
                ),
                reviewer_name=settings.approval_default_reviewer,
                final_approver_name=settings.approval_default_final_approver,
                sla_hours=48,
                active=True,
            )
        )

    defaults = {
        "notification_retention_days": ("90", "Prazo de retenção das notificações internas."),
        "approval_reminder_hours": ("24", "Intervalo para lembretes de aprovação."),
        "access_request_approver": (settings.approval_default_final_approver, "Responsável padrão por solicitações de acesso."),
        "default_environment_label": (settings.app_env.upper(), "Rótulo visual do ambiente."),
    }
    existing_keys = set(db.scalars(select(AppSetting.key)).all())
    for key, (value, description) in defaults.items():
        if key not in existing_keys:
            db.add(AppSetting(key=key, value=value, description=description))
    db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    return item.value if item else default


def set_setting(db: Session, key: str, value: str, description: str = "") -> AppSetting:
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if not item:
        item = AppSetting(key=key, value=value, description=description)
        db.add(item)
    else:
        item.value = value
        if description:
            item.description = description
    db.commit()
    db.refresh(item)
    return item


def create_notification(
    db: Session,
    recipient: str,
    title: str,
    message: str,
    category: str = "info",
    link: str = "",
) -> Notification:
    notification = Notification(
        recipient=recipient or "Todos",
        title=title,
        message=message,
        category=category,
        link=link,
    )
    db.add(notification)
    return notification


def active_approval_flow(db: Session) -> ApprovalFlowDefinition | None:
    return db.scalar(
        select(ApprovalFlowDefinition)
        .where(ApprovalFlowDefinition.active.is_(True))
        .order_by(ApprovalFlowDefinition.id)
    )


def current_pending_request(db: Session, process_id: int) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.process_id == process_id, ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.stage_order.desc(), ApprovalRequest.created_at.desc())
    )


def create_first_approval_request(db: Session, process: ProcessSpecification, requested_by: str) -> ApprovalRequest:
    flow = active_approval_flow(db)
    reviewer = flow.reviewer_name if flow else settings.approval_default_reviewer
    item = ApprovalRequest(
        process_id=process.id,
        flow_id=flow.id if flow else None,
        stage_order=1,
        stage_name="Revisão técnica",
        requested_by=requested_by,
        assigned_to=reviewer,
        status="pending",
    )
    db.add(item)
    create_notification(
        db,
        reviewer,
        f"Revisão pendente: {process.code}",
        f"{requested_by} enviou o processo “{process.name}” para revisão técnica.",
        category="approval",
        link=f"/processes/{process.id}",
    )
    return item


def move_to_next_approval_stage(
    db: Session,
    process: ProcessSpecification,
    current: ApprovalRequest,
    actor: str,
) -> ApprovalRequest | None:
    flow = current.flow or active_approval_flow(db)
    if current.stage_order == 1 and flow and flow.final_approver_name:
        next_request = ApprovalRequest(
            process_id=process.id,
            flow_id=flow.id,
            stage_order=2,
            stage_name="Aprovação final",
            requested_by=current.requested_by,
            assigned_to=flow.final_approver_name,
            status="pending",
        )
        db.add(next_request)
        create_notification(
            db,
            flow.final_approver_name,
            f"Aprovação final pendente: {process.code}",
            f"{actor} concluiu a revisão técnica do processo “{process.name}”.",
            category="approval",
            link=f"/processes/{process.id}",
        )
        return next_request
    return None


def complete_approval_request(request: ApprovalRequest, actor: str, status: str, note: str = "") -> None:
    request.status = status
    request.decision_by = actor
    request.decision_note = note
    request.decided_at = datetime.now(UTC)


def emit_n8n_event(
    db: Session,
    process: ProcessSpecification,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Mantém a API anterior, mas agora utiliza outbox assíncrona e idempotente."""
    if not settings.n8n_enabled:
        return {"status": "disabled", "job_id": None}
    job = enqueue_job(
        db,
        provider="n8n",
        event_name=event_name,
        payload=payload,
        process_id=process.id,
        correlation_id=process.correlation_id,
        idempotency_key=f"n8n:{event_name}:{process.correlation_id}:v{process.version}",
    )
    return {"status": job.status, "job_id": job.id}
