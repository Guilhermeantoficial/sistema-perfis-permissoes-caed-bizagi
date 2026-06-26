from fastapi.testclient import TestClient

from app.main import app


def test_all_navigation_pages_are_available():
    paths = [
        "/",
        "/processes",
        "/profiles",
        "/permissions",
        "/users",
        "/units",
        "/roles",
        "/approval-flows",
        "/settings",
        "/integrations",
        "/audit-logs",
        "/documentation",
        "/help",
        "/notifications",
    ]
    with TestClient(app) as client:
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200, path
            assert "text/html" in response.headers.get("content-type", ""), path


def test_help_and_notification_api():
    with TestClient(app) as client:
        notifications = client.get("/api/notifications")
        assert notifications.status_code == 200
        assert "items" in notifications.json()
