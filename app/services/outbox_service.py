from __future__ import annotations

import json
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.bizagi import BizagiClient
from app.integrations.email import EmailClient
from app.integrations.n8n import N8nClient
from app.metrics import INTEGRATION_RESULTS
from app.models import AuditEvent, IntegrationJob, ProcessSpecification
from app.services.process_service import serialize_process


def utcnow() -> datetime:
    return datetime.now(UTC)


def enqueue_job(
    db: Session,
    *,
    provider: str,
    event_name: str,
    payload: dict[str, Any],
    process_id: int | None = None,
    correlation_id: str = "",
    idempotency_key: str | None = None,
    max_attempts: int | None = None,
) -> IntegrationJob:
    key = idempotency_key or f"{provider}:{event_name}:{correlation_id or uuid.uuid4()}"
    existing = db.scalar(select(IntegrationJob).where(IntegrationJob.idempotency_key == key))
    if existing:
        return existing
    job = IntegrationJob(
        process_id=process_id,
        provider=provider,
        event_name=event_name,
        status="pending",
        idempotency_key=key,
        correlation_id=correlation_id,
        max_attempts=max_attempts or settings.worker_max_attempts,
        request_json=json.dumps(payload, ensure_ascii=False, default=str),
        next_attempt_at=utcnow(),
    )
    db.add(job)
    db.flush()
    return job


def claim_jobs(db: Session, worker_id: str, limit: int | None = None) -> list[IntegrationJob]:
    now = utcnow()
    lock_expired = now - timedelta(seconds=settings.worker_lock_timeout_seconds)
    query = (
        select(IntegrationJob)
        .where(
            IntegrationJob.status.in_(["pending", "retrying"]),
            IntegrationJob.next_attempt_at <= now,
            or_(IntegrationJob.locked_at.is_(None), IntegrationJob.locked_at < lock_expired),
        )
        .order_by(IntegrationJob.created_at)
        .limit(limit or settings.worker_batch_size)
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    jobs = list(db.scalars(query).all())
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id
    db.commit()
    return jobs


def _retry_delay(attempt: int) -> int:
    return min(
        settings.worker_backoff_max_seconds,
        settings.worker_backoff_base_seconds * (2 ** max(0, attempt - 1)),
    )


def process_job(db: Session, job: IntegrationJob) -> None:
    job.attempt_count += 1
    payload = json.loads(job.request_json or "{}")
    try:
        if job.provider == "n8n":
            result = N8nClient().send_event(job.event_name, payload, idempotency_key=job.idempotency_key)
            response: dict[str, Any] = result.raw
        elif job.provider == "bizagi":
            process = db.get(ProcessSpecification, job.process_id) if job.process_id else None
            if not process:
                raise RuntimeError("Processo não encontrado para integração Bizagi.")
            if process.status != "approved":
                raise RuntimeError("Somente processos aprovados podem ser enviados ao Bizagi.")
            business_payload = serialize_process(process)
            result = BizagiClient().start_case(business_payload, idempotency_key=job.idempotency_key)
            process.status = "synced"
            process.bizagi_sync_status = "completed"
            process.bizagi_case_id = result.case_id
            response = result.raw
            db.add(
                AuditEvent(
                    process_id=process.id,
                    action="bizagi_synced",
                    actor="Worker de integração",
                    category="integration",
                    details_json=json.dumps({"case_id": result.case_id, "job_id": job.id}),
                )
            )
        elif job.provider == "email":
            EmailClient().send(
                recipient=str(payload["recipient"]),
                subject=str(payload["subject"]),
                body=str(payload["body"]),
            )
            response = {"sent": True}
        else:
            raise RuntimeError(f"Provedor de integração desconhecido: {job.provider}")

        job.status = "completed"
        INTEGRATION_RESULTS.labels(provider=job.provider, event=job.event_name, result="completed").inc()
        job.response_json = json.dumps(response, ensure_ascii=False, default=str)
        job.error_message = ""
        job.completed_at = utcnow()
        job.locked_at = None
        job.locked_by = ""
        db.commit()
    except Exception as exc:
        job.error_message = str(exc)[:4000]
        job.locked_at = None
        job.locked_by = ""
        if job.attempt_count >= job.max_attempts:
            job.status = "failed"
        else:
            job.status = "retrying"
            job.next_attempt_at = utcnow() + timedelta(seconds=_retry_delay(job.attempt_count))
        INTEGRATION_RESULTS.labels(provider=job.provider, event=job.event_name, result=job.status).inc()
        if job.process_id:
            process = db.get(ProcessSpecification, job.process_id)
            if process and job.provider == "bizagi":
                process.bizagi_sync_status = "failed" if job.status == "failed" else "retrying"
        db.commit()


def worker_identity() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
