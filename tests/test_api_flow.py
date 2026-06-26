from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import ProcessSpecification
from tests.helpers import csrf_headers


def test_complete_process_flow_and_exports():
    code = f"TST-{uuid4().hex[:8].upper()}"
    process_id = None

    try:
        with TestClient(app) as client:
            headers = csrf_headers(client)
            created = client.post(
                "/api/processes",
                json={
                    "code": code,
                    "name": "Processo automatizado de teste",
                    "responsible": "Equipe de QA",
                    "area": "Qualidade de Software",
                    "description": "Validação integrada da API.",
                    "source_document": "",
                    "actor": "Pytest",
                },
                headers=headers,
            )
            assert created.status_code == 201
            process_id = created.json()["process"]["id"]

            duplicate = client.post(
                "/api/processes",
                json={"code": code, "name": "Código duplicado", "actor": "Pytest"},
                headers=headers,
            )
            assert duplicate.status_code == 409

            saved = client.put(
                f"/api/processes/{process_id}/matrix",
                json={
                    "code": code,
                    "name": "Processo automatizado de teste",
                    "responsible": "Equipe de QA",
                    "area": "Qualidade de Software",
                    "description": "Validação integrada da API.",
                    "source_document": "",
                    "actor": "Pytest",
                    "row_version": created.json()["process"]["row_version"],
                    "profiles": [
                        {
                            "hierarchy": "Estado",
                            "profile_name": "Analista de teste",
                            "agent_type": "Usuário",
                            "source_reference": "Cadastro manual",
                            "permissions": ["EDIT"],
                        }
                    ],
                },
                headers=headers,
            )
            assert saved.status_code == 200
            profile = saved.json()["process"]["profiles"][0]
            assert profile["permissions"] == ["VIEW", "EDIT"]
            assert saved.json()["process"]["area"] == "Qualidade de Software"

            submitted = client.post(
                f"/api/processes/{process_id}/submit", json={"actor": "Pytest"}, headers=headers
            )
            assert submitted.status_code == 200
            assert submitted.json()["process"]["status"] == "pending_approval"

            reviewed = client.post(
                f"/api/processes/{process_id}/approve", json={"actor": "Pytest"}, headers=headers
            )
            assert reviewed.status_code == 200
            assert reviewed.json()["process"]["status"] == "pending_approval"
            assert reviewed.json()["process"]["current_approval"]["stage_order"] == 2

            approved = client.post(
                f"/api/processes/{process_id}/approve", json={"actor": "Pytest final"}, headers=headers
            )
            assert approved.status_code == 200
            assert approved.json()["process"]["status"] == "approved"

            payload = client.get(f"/api/processes/{process_id}/bizagi/payload")
            assert payload.status_code == 200
            assert payload.json()["business_payload"]["code"] == code

            for extension, content_type in (
                ("json", "application/json"),
                ("csv", "text/csv"),
                (
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ):
                exported = client.get(
                    f"/api/processes/{process_id}/export/{extension}"
                )
                assert exported.status_code == 200
                assert content_type in exported.headers["content-type"]
                assert exported.content
    finally:
        if process_id is not None:
            with SessionLocal() as db:
                process = db.scalar(
                    select(ProcessSpecification).where(
                        ProcessSpecification.id == process_id
                    )
                )
                if process:
                    db.delete(process)
                    db.commit()
