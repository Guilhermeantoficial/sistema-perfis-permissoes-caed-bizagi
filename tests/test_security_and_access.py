from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AccessRequest, IntegrationJob, UserAccount
from app.services.outbox_service import enqueue_job
from tests.helpers import csrf_headers


def test_csrf_rejects_missing_token():
    with TestClient(app) as client:
        response = client.post('/api/processes', json={'code': 'NO-CSRF', 'name': 'Sem token'})
        assert response.status_code == 403


def test_access_request_can_be_created_and_approved():
    with TestClient(app) as client:
        csrf_headers(client)
        response = client.post(
            '/access-requests',
            data={
                'requested_role': '',
                'requested_permissions': 'audit.read',
                'justification': 'Necessário para auditoria formal do processo de homologação.',
                '_csrf': client.cookies.get('caed_pp_csrf'),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    with SessionLocal() as db:
        item = db.scalar(select(AccessRequest).order_by(AccessRequest.id.desc()))
        assert item is not None
        assert item.status == 'pending'
        request_id = item.id

    with TestClient(app) as client:
        token = csrf_headers(client)['X-CSRF-Token']
        response = client.post(
            f'/api/access-requests/{request_id}/approve',
            data={'note': 'Aprovado no teste.', '_csrf': token},
            follow_redirects=False,
        )
        assert response.status_code == 303

    with SessionLocal() as db:
        item = db.get(AccessRequest, request_id)
        admin = db.scalar(select(UserAccount).where(UserAccount.email == 'guilhermeantoniooficial@gmail.com'))
        assert item.status == 'approved'
        assert admin is not None


def test_outbox_is_idempotent():
    with SessionLocal() as db:
        first = enqueue_job(
            db,
            provider='n8n',
            event_name='integration.test',
            payload={'ok': True},
            idempotency_key='pytest-idempotency-key',
            correlation_id='pytest-correlation',
        )
        db.commit()
        second = enqueue_job(
            db,
            provider='n8n',
            event_name='integration.test',
            payload={'ok': True},
            idempotency_key='pytest-idempotency-key',
            correlation_id='pytest-correlation',
        )
        db.commit()
        assert first.id == second.id
        assert db.scalar(select(IntegrationJob).where(IntegrationJob.idempotency_key == 'pytest-idempotency-key'))
