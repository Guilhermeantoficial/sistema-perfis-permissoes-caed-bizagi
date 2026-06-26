from __future__ import annotations

from uuid import uuid4

from app.authorization import has_permission, required_permission_for_request
from app.database import SessionLocal
from app.models import UserAccount


def test_role_permissions_are_enforced_server_side():
    email = f"reader-{uuid4().hex[:8]}@example.test"
    with SessionLocal() as db:
        user = UserAccount(name="Leitor", email=email, role_name="Usuário", unit_name="Teste")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert has_permission(db, user, "process.read")
        assert has_permission(db, user, "access.request")
        assert not has_permission(db, user, "process.create")
        assert not has_permission(db, user, "settings.manage")
        db.delete(user)
        db.commit()


def test_sensitive_routes_require_expected_permissions():
    assert required_permission_for_request("POST", "/api/processes/1/matrix") == "process.edit"
    assert required_permission_for_request("POST", "/api/processes/1/approve") == "process.approve"
    assert required_permission_for_request("POST", "/api/processes/1/bizagi/sync") == "integration.execute"
    assert required_permission_for_request("POST", "/api/access-requests/1/approve") == "access.approve"
    assert required_permission_for_request("POST", "/api/integration-jobs/1/retry") == "integration.execute"
