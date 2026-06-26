from __future__ import annotations

from fastapi.testclient import TestClient


def csrf_headers(client: TestClient) -> dict[str, str]:
    client.get('/health')
    token = client.cookies.get('caed_pp_csrf')
    assert token
    return {'X-CSRF-Token': token}
