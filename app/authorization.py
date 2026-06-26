from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoleDefinition, UserAccount, UserPermissionGrant

ALL_PERMISSIONS = {
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
}

DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Administrador": set(ALL_PERMISSIONS),
    "Solicitante": {
        "process.read", "process.create", "process.edit", "process.submit", "process.export",
        "access.request", "notification.read",
    },
    "Revisor": {
        "process.read", "process.approve", "process.export", "audit.read",
        "access.request", "notification.read",
    },
    "Aprovador": {
        "process.read", "process.approve", "process.reopen", "process.export",
        "integration.read", "integration.execute", "audit.read", "access.approve",
        "access.request", "notification.read",
    },
    "Auditor": {
        "process.read", "process.export", "integration.read", "audit.read", "notification.read",
    },
    "Usuário": {"process.read", "access.request", "notification.read"},
}


def permissions_for_user(db: Session, user: UserAccount | None, process_id: int | None = None) -> set[str]:
    if not user:
        return set()
    permissions = set(DEFAULT_ROLE_PERMISSIONS.get(user.role_name, DEFAULT_ROLE_PERMISSIONS["Usuário"]))
    role = db.scalar(select(RoleDefinition).where(RoleDefinition.name == user.role_name))
    if role and role.permission_codes_json:
        try:
            configured = set(json.loads(role.permission_codes_json))
            if configured:
                permissions = configured
        except (TypeError, json.JSONDecodeError):
            pass

    now = datetime.now(UTC)
    grants = db.scalars(
        select(UserPermissionGrant).where(
            UserPermissionGrant.user_id == user.id,
            (UserPermissionGrant.process_id.is_(None))
            | (UserPermissionGrant.process_id == process_id),
        )
    ).all()
    for grant in grants:
        if grant.expires_at is None or grant.expires_at > now:
            permissions.add(grant.permission_code)
    return permissions


def has_permission(db: Session, user: UserAccount | None, permission: str, process_id: int | None = None) -> bool:
    return permission in permissions_for_user(db, user, process_id)


def required_permission_for_request(method: str, path: str) -> str | None:
    """Mapeamento central de autorização para UI e API.

    As regras mais específicas devem vir primeiro.
    """
    if path.startswith("/static") or path in {"/login", "/auth/oidc", "/auth/callback", "/logout"}:
        return None
    if path.startswith("/health") or path == "/metrics" or path.startswith("/api/n8n/callback"):
        return None
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc"):
        return None

    if path.startswith("/api/access-requests/") and method == "POST":
        return "access.approve"
    if path.startswith("/access-requests"):
        return "access.request"
    if path.startswith("/api/processes/") and "/approve" in path:
        return "process.approve"
    if path.startswith("/api/processes/") and "/reject" in path:
        return "process.approve"
    if path.startswith("/api/processes/") and "/reopen" in path:
        return "process.reopen"
    if path.startswith("/api/processes/") and "/submit" in path:
        return "process.submit"
    if path.startswith("/api/processes/") and "/matrix" in path:
        return "process.edit"
    if path.startswith("/api/processes/") and "/bizagi/sync" in path:
        return "integration.execute"
    if path.startswith("/api/processes/") and "/bizagi/" in path:
        return "integration.read"
    if path.startswith("/api/processes/") and "/export/" in path:
        return "process.export"
    if path == "/api/processes" and method == "POST":
        return "process.create"
    if path.startswith("/api/processes"):
        return "process.read"

    if path.startswith("/users"):
        return "user.manage"
    if path.startswith("/units"):
        return "unit.manage"
    if path.startswith("/roles"):
        return "role.manage"
    if path.startswith("/approval-flows"):
        return "approval.manage"
    if path.startswith("/settings"):
        return "settings.manage"
    if path.startswith("/api/integration-jobs/"):
        return "integration.execute"
    if path.startswith("/integrations"):
        return "integration.read" if method == "GET" else "integration.execute"
    if path.startswith("/audit-logs"):
        return "audit.read"
    if path.startswith("/notifications") or path.startswith("/api/notifications"):
        return "notification.read"
    if path.startswith("/documentation") or path.startswith("/help"):
        return "process.read"
    if path == "/" or path.startswith("/processes") or path.startswith("/profiles") or path.startswith("/permissions"):
        return "process.read"
    return "process.read"
