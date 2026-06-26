from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccessRequest, Notification, UserAccount, UserPermissionGrant


def create_access_request(
    db: Session,
    *,
    requester: UserAccount,
    process_id: int | None,
    requested_role: str,
    requested_permissions: list[str],
    justification: str,
    expires_at=None,
    assigned_to: str = "",
) -> AccessRequest:
    item = AccessRequest(
        requester_id=requester.id,
        process_id=process_id,
        requested_role=requested_role,
        requested_permissions_json=json.dumps(requested_permissions, ensure_ascii=False),
        justification=justification,
        assigned_to=assigned_to,
        expires_at=expires_at,
    )
    db.add(item)
    db.add(
        Notification(
            recipient=assigned_to or "Todos",
            title="Nova solicitação de acesso",
            message=f"{requester.name} solicitou acesso adicional.",
            category="approval",
            link="/access-requests",
        )
    )
    db.commit()
    db.refresh(item)
    return item


def approve_access_request(db: Session, item: AccessRequest, approver: UserAccount, note: str = "") -> None:
    if item.status != "pending":
        raise ValueError("A solicitação já foi decidida.")
    requester = db.get(UserAccount, item.requester_id)
    if not requester:
        raise ValueError("Usuário solicitante não encontrado.")
    permissions = json.loads(item.requested_permissions_json or "[]")
    if item.requested_role:
        requester.role_name = item.requested_role
    for permission_code in permissions:
        existing = db.scalar(
            select(UserPermissionGrant).where(
                UserPermissionGrant.user_id == requester.id,
                UserPermissionGrant.process_id == item.process_id,
                UserPermissionGrant.permission_code == permission_code,
            )
        )
        if not existing:
            db.add(
                UserPermissionGrant(
                    user_id=requester.id,
                    process_id=item.process_id,
                    permission_code=permission_code,
                    granted_by=approver.email,
                    expires_at=item.expires_at,
                )
            )
    item.status = "approved"
    item.decision_by = approver.email
    item.decision_note = note
    item.decided_at = datetime.now(UTC)
    db.add(
        Notification(
            recipient=requester.email,
            title="Solicitação de acesso aprovada",
            message=note or "As permissões solicitadas foram concedidas.",
            category="success",
            link="/access-requests",
        )
    )
    db.commit()


def reject_access_request(db: Session, item: AccessRequest, approver: UserAccount, note: str = "") -> None:
    if item.status != "pending":
        raise ValueError("A solicitação já foi decidida.")
    requester = db.get(UserAccount, item.requester_id)
    item.status = "rejected"
    item.decision_by = approver.email
    item.decision_note = note
    item.decided_at = datetime.now(UTC)
    if requester:
        db.add(
            Notification(
                recipient=requester.email,
                title="Solicitação de acesso não aprovada",
                message=note or "A solicitação foi recusada pelo responsável.",
                category="warning",
                link="/access-requests",
            )
        )
    db.commit()
