from app.services.process_service import apply_permission_dependencies, permission_summary


def test_edit_requires_view():
    assert apply_permission_dependencies(["EDIT"]) == ["VIEW", "EDIT"]


def test_approve_requires_view_and_monitor():
    assert apply_permission_dependencies(["APPROVE"]) == ["VIEW", "MONITOR", "APPROVE"]


def test_admin_grants_everything():
    assert apply_permission_dependencies(["ADMINISTER"]) == [
        "VIEW", "REGISTER", "EDIT", "DELETE", "MONITOR", "APPROVE", "ADMINISTER"
    ]


def test_empty_summary():
    assert permission_summary([]) == "Não se aplica"
