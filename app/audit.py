from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent, UserAccount


def audit_event(
    db: Session,
    *,
    action: str,
    actor: UserAccount | None = None,
    process_id: int | None = None,
    category: str = "business",
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    event = AuditEvent(
        process_id=process_id,
        category=category,
        action=action,
        actor=actor.name if actor else "Sistema",
        actor_email=actor.email if actor else "",
        request_id=getattr(request.state, "request_id", "") if request else "",
        ip_address=(request.client.host if request and request.client else ""),
        details_json=json.dumps(details or {}, ensure_ascii=False, default=str),
    )
    db.add(event)
    return event
