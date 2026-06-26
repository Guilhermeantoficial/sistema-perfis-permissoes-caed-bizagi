from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ApprovalRequest, AuditEvent, ProcessSpecification, ProfileDefinition, ProfilePermission
from app.schemas import MatrixUpdate, ProcessCreate

PERMISSION_LABELS = {
    "VIEW": "Visualizar",
    "REGISTER": "Registrar",
    "EDIT": "Editar",
    "DELETE": "Excluir",
    "MONITOR": "Monitorar",
    "APPROVE": "Aprovar",
    "ADMINISTER": "Administrar",
}


SOURCE_PROFILES = [
    ("Estado", "Candidato a Coordenador", "Não se aplica", "Não se aplica", []),
    ("Estado", "Candidato a Aplicador", "Não se aplica", "Não se aplica", []),
    ("Estado", "Cursista Aplicador", "Não se aplica", "Não se aplica", []),
    ("Estado", "Cursista Coordenador", "Não se aplica", "Não se aplica", []),
    ("Estado", "Coordenação Estadual da Avaliação", "Não se aplica", "Não se aplica", []),
    ("Regional", "Coordenação Regional da Avaliação", "Não se aplica", "Não se aplica", []),
    (
        "Municipal",
        "Coordenação Municipal da Avaliação",
        "Coordenador Municipal da avaliação",
        "Monitora as ocorrências registradas no processo avaliativo",
        ["VIEW", "MONITOR"],
    ),
    (
        "Estado",
        "Coordenação de Polo da Avaliação",
        "Coordenador de Polo Regional",
        "Registra as ocorrências identificadas no processo avaliativo",
        ["VIEW", "REGISTER"],
    ),
    ("País/Estado/Município", "CAEd - Suporte", "Não se aplica", "Não se aplica", []),
    ("País/Estado/Município", "CAEd - ADM Dados", "Não se aplica", "Não se aplica", []),
    ("País/Estado/Município", "CAEd - Design", "Não se aplica", "Não se aplica", []),
    (
        "País/Estado/Município",
        "CAEd - Organização do Campo",
        "Não se aplica",
        "Monitora as ocorrências registradas no processo avaliativo",
        ["VIEW", "MONITOR"],
    ),
    (
        "País/Estado/Município",
        "CAEd - Logística e Monitoramento",
        "Não se aplica",
        "Monitora as ocorrências registradas no processo avaliativo",
        ["VIEW", "MONITOR"],
    ),
    ("País/Estado/Município", "CAEd - Visitante", "Não se aplica", "Não se aplica", []),
]


def apply_permission_dependencies(codes: Iterable[str]) -> list[str]:
    result = set(codes)
    if result & {"REGISTER", "EDIT", "DELETE", "MONITOR", "APPROVE", "ADMINISTER"}:
        result.add("VIEW")
    if "APPROVE" in result:
        result.add("MONITOR")
    if "ADMINISTER" in result:
        result.update(PERMISSION_LABELS)
    return [code for code in PERMISSION_LABELS if code in result]


def permission_summary(codes: Iterable[str]) -> str:
    normalized = apply_permission_dependencies(codes)
    if not normalized:
        return "Não se aplica"
    return ", ".join(PERMISSION_LABELS[code] for code in normalized)


def add_audit(
    db: Session,
    process_id: int | None,
    action: str,
    actor: str,
    details: dict,
    *,
    actor_email: str = "",
    request_id: str = "",
    ip_address: str = "",
    category: str = "business",
) -> None:
    db.add(
        AuditEvent(
            process_id=process_id,
            category=category,
            action=action,
            actor=actor or "Sistema",
            actor_email=actor_email,
            request_id=request_id,
            ip_address=ip_address,
            details_json=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


def create_process(db: Session, payload: ProcessCreate) -> ProcessSpecification:
    code = payload.code.strip()
    existing = db.scalar(select(ProcessSpecification).where(ProcessSpecification.code == code))
    if existing:
        raise ValueError(f"Já existe um processo com o código {code}.")

    actor = payload.actor.strip() or "Usuário autenticado"
    process = ProcessSpecification(
        code=code,
        name=payload.name.strip(),
        description=payload.description.strip(),
        responsible=payload.responsible.strip(),
        area=payload.area.strip(),
        source_document=payload.source_document.strip(),
        status="draft",
        bizagi_sync_status="not_configured",
        created_by=actor,
        updated_by=actor,
    )
    db.add(process)
    db.flush()
    add_audit(
        db,
        process.id,
        "process_created",
        actor,
        {"mode": "manual", "source_document": process.source_document or None},
    )
    db.commit()
    return get_process(db, process.id)


def ensure_seed_data(db: Session) -> ProcessSpecification:
    process = db.scalar(select(ProcessSpecification).where(ProcessSpecification.code == "2326"))
    if process:
        return process

    process = ProcessSpecification(
        code="2326",
        name="BA Salvador – Avaliação Diagnóstica 2026 (Prosa Percurso)",
        description=(
            "Matriz inicial de perfis e permissões do Card Ocorrências. "
            "Todos os dados podem ser alterados diretamente no sistema."
        ),
        responsible="Supervisão de Planejamento e Protocolos",
        area="Avaliação, Monitoramento e Desenvolvimento Profissional",
        source_document="2276-P06-Protocolos-Ocorrências_R1.docx",
        status="draft",
        bizagi_sync_status="not_configured",
        created_by="Sistema",
        updated_by="Sistema",
    )
    db.add(process)
    db.flush()

    for order, (hierarchy, profile, agent, summary, permissions) in enumerate(SOURCE_PROFILES, start=1):
        row = ProfileDefinition(
            process_id=process.id,
            hierarchy=hierarchy,
            profile_name=profile,
            agent_type=agent,
            permission_summary=summary,
            source_reference="Documento, p. 4",
            sort_order=order,
        )
        db.add(row)
        db.flush()
        for code in apply_permission_dependencies(permissions):
            db.add(ProfilePermission(profile_id=row.id, permission_code=code))

    add_audit(
        db,
        process.id,
        "seed_created",
        "Sistema",
        {"source": process.source_document, "profiles": len(SOURCE_PROFILES)},
    )
    db.commit()
    return process


def get_process(db: Session, process_id: int) -> ProcessSpecification | None:
    return db.scalar(
        select(ProcessSpecification)
        .options(
            selectinload(ProcessSpecification.profiles).selectinload(ProfileDefinition.permissions),
            selectinload(ProcessSpecification.audit_events),
            selectinload(ProcessSpecification.integration_jobs),
            selectinload(ProcessSpecification.approval_requests).selectinload(ApprovalRequest.flow),
        )
        .where(ProcessSpecification.id == process_id)
    )


def serialize_process(process: ProcessSpecification) -> dict:
    return {
        "id": process.id,
        "public_id": process.public_id,
        "correlation_id": process.correlation_id,
        "code": process.code,
        "name": process.name,
        "description": process.description,
        "responsible": process.responsible,
        "area": process.area,
        "source_document": process.source_document,
        "status": process.status,
        "version": process.version,
        "row_version": process.row_version,
        "created_by": process.created_by,
        "updated_by": process.updated_by,
        "approved_by": process.approved_by,
        "approved_at": process.approved_at.isoformat() if process.approved_at else None,
        "bizagi_case_id": process.bizagi_case_id,
        "bizagi_sync_status": process.bizagi_sync_status,
        "created_at": process.created_at.isoformat(),
        "updated_at": process.updated_at.isoformat(),
        "profiles": [
            {
                "id": profile.id,
                "hierarchy": profile.hierarchy,
                "profile_name": profile.profile_name,
                "agent_type": profile.agent_type,
                "permission_summary": profile.permission_summary,
                "source_reference": profile.source_reference,
                "notes": profile.notes,
                "permissions": sorted(
                    (permission.permission_code for permission in profile.permissions),
                    key=lambda code: list(PERMISSION_LABELS).index(code),
                ),
            }
            for profile in process.profiles
        ],
        "audit_events": [
            {
                "action": event.action,
                "category": event.category,
                "actor": event.actor,
                "actor_email": event.actor_email,
                "request_id": event.request_id,
                "details": json.loads(event.details_json or "{}"),
                "created_at": event.created_at.isoformat(),
            }
            for event in sorted(process.audit_events, key=lambda item: item.created_at, reverse=True)
        ],
        "approval_requests": [
            {
                "id": request.id,
                "stage_order": request.stage_order,
                "stage_name": request.stage_name,
                "requested_by": request.requested_by,
                "assigned_to": request.assigned_to,
                "status": request.status,
                "decision_by": request.decision_by,
                "decision_note": request.decision_note,
                "created_at": request.created_at.isoformat(),
                "decided_at": request.decided_at.isoformat() if request.decided_at else None,
                "flow_name": request.flow.name if request.flow else "Fluxo padrão",
            }
            for request in sorted(process.approval_requests, key=lambda item: (item.stage_order, item.created_at))
        ],
        "current_approval": next(
            (
                {
                    "id": request.id,
                    "stage_order": request.stage_order,
                    "stage_name": request.stage_name,
                    "assigned_to": request.assigned_to,
                    "requested_by": request.requested_by,
                    "created_at": request.created_at.isoformat(),
                    "flow_name": request.flow.name if request.flow else "Fluxo padrão",
                }
                for request in sorted(process.approval_requests, key=lambda item: item.created_at, reverse=True)
                if request.status == "pending"
            ),
            None,
        ),
        "integration_jobs": [
            {
                "id": job.id,
                "provider": job.provider,
                "event_name": job.event_name,
                "status": job.status,
                "attempt_count": job.attempt_count,
                "max_attempts": job.max_attempts,
                "error_message": job.error_message,
                "idempotency_key": job.idempotency_key,
                "created_at": job.created_at.isoformat(),
            }
            for job in sorted(process.integration_jobs, key=lambda item: item.created_at, reverse=True)
        ],
    }


def validate_matrix(payload: MatrixUpdate) -> list[str]:
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, profile in enumerate(payload.profiles, start=1):
        key = (profile.hierarchy.strip().casefold(), profile.profile_name.strip().casefold())
        if key in seen:
            raise ValueError(
                f"Perfil duplicado na linha {index}: {profile.hierarchy} / {profile.profile_name}."
            )
        seen.add(key)
        normalized = apply_permission_dependencies(profile.permissions)
        if not normalized and profile.permission_summary.strip().casefold() != "não se aplica":
            warnings.append(f"{profile.profile_name}: há descrição de permissão, mas nenhuma ação foi marcada.")
        if normalized and profile.permission_summary.strip().casefold() == "não se aplica":
            warnings.append(f"{profile.profile_name}: possui ações marcadas; a descrição será recalculada.")
    return warnings


def replace_matrix(db: Session, process: ProcessSpecification, payload: MatrixUpdate) -> list[str]:
    if process.status != "draft":
        raise ValueError("Somente processos em rascunho podem ser editados. Reabra a versão antes de alterar.")
    if payload.row_version is not None and payload.row_version != process.row_version:
        raise ValueError(
            "O processo foi alterado por outra pessoa. Atualize a página antes de salvar novamente."
        )

    duplicate_code = db.scalar(
        select(ProcessSpecification).where(
            ProcessSpecification.code == payload.code.strip(),
            ProcessSpecification.id != process.id,
        )
    )
    if duplicate_code:
        raise ValueError(f"Já existe outro processo com o código {payload.code.strip()}.")

    warnings = validate_matrix(payload)
    process.code = payload.code.strip()
    process.name = payload.name.strip()
    process.description = payload.description.strip()
    process.responsible = payload.responsible.strip()
    process.area = payload.area.strip()
    process.source_document = payload.source_document.strip()
    process.version += 1
    process.row_version += 1
    process.updated_by = payload.actor.strip() or "Usuário autenticado"

    process.profiles.clear()
    db.flush()

    for order, item in enumerate(payload.profiles, start=1):
        normalized = apply_permission_dependencies(item.permissions)
        row = ProfileDefinition(
            process_id=process.id,
            hierarchy=item.hierarchy.strip(),
            profile_name=item.profile_name.strip(),
            agent_type=item.agent_type.strip() or "Não se aplica",
            permission_summary=permission_summary(normalized),
            source_reference=item.source_reference.strip() or "Cadastro manual",
            notes=item.notes.strip(),
            sort_order=order,
        )
        db.add(row)
        db.flush()
        for code in normalized:
            db.add(ProfilePermission(profile_id=row.id, permission_code=code))

    add_audit(
        db,
        process.id,
        "matrix_saved",
        payload.actor,
        {
            "version": process.version,
            "row_version": process.row_version,
            "profiles": len(payload.profiles),
            "warnings": warnings,
            "source_document": process.source_document or None,
        },
    )
    db.commit()
    db.expire_all()
    return warnings
