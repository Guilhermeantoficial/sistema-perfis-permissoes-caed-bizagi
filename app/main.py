from __future__ import annotations

import hashlib
import json
import secrets
from collections import Counter
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth import (
    authenticate_local,
    hash_password,
    login_session,
    logout_session,
    oauth,
    register_oidc_client,
    upsert_oidc_user,
)
from app.authorization import ALL_PERMISSIONS, has_permission, permissions_for_user
from app.config import BASE_DIR, settings
from app.database import SessionLocal, database_ready, get_db, run_migrations
from app.integrations.bizagi import BizagiClient
from app.integrations.n8n import N8nClient, verify_callback_signature
from app.logging_config import configure_logging
from app.metrics import MetricsMiddleware
from app.middleware import (
    AuthorizationMiddleware,
    CsrfMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.models import (
    AccessRequest,
    ApprovalFlowDefinition,
    ApprovalRequest,
    AppSetting,
    AuditEvent,
    IntegrationJob,
    Notification,
    OrganizationalUnit,
    ProcessSpecification,
    ProfileDefinition,
    ProfilePermission,
    RoleDefinition,
    UserAccount,
    WebhookReceipt,
)
from app.schemas import (
    AccessRequestCreate,
    ActorInput,
    DecisionInput,
    MatrixUpdate,
    N8nCallbackInput,
    ProcessCreate,
)
from app.services.access_request_service import (
    approve_access_request,
    create_access_request,
    reject_access_request,
)
from app.services.admin_service import (
    active_approval_flow,
    complete_approval_request,
    create_first_approval_request,
    create_notification,
    current_pending_request,
    emit_n8n_event,
    ensure_admin_seed,
    get_setting,
    move_to_next_approval_stage,
    set_setting,
)
from app.services.export_service import process_to_csv_bytes, process_to_docx_bytes, process_to_json_bytes
from app.services.outbox_service import enqueue_job
from app.services.process_service import (
    PERMISSION_LABELS,
    add_audit,
    create_process,
    ensure_seed_data,
    get_process,
    replace_matrix,
    serialize_process,
)

configure_logging()
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )

ACTION_LABELS = {
    "seed_created": "Base inicial criada",
    "process_created": "Processo criado",
    "matrix_saved": "Matriz de permissões atualizada",
    "submitted_for_approval": "Processo enviado para aprovação",
    "approval_stage_completed": "Etapa de aprovação concluída",
    "approved": "Processo aprovado",
    "rejected": "Processo devolvido para ajustes",
    "reopened": "Processo reaberto para edição",
    "bizagi_simulated": "Integração com Bizagi simulada",
    "bizagi_queued": "Integração com Bizagi enfileirada",
    "bizagi_synced": "Integração com Bizagi concluída",
    "bizagi_sync_failed": "Falha na integração com Bizagi",
    "n8n_callback": "Retorno recebido do n8n",
    "integration_requeued": "Job de integração reenfileirado",
    "access_requested": "Acesso solicitado",
    "access_approved": "Acesso aprovado",
    "access_rejected": "Acesso recusado",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.run_migrations_on_startup:
        run_migrations()
    register_oidc_client()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            ensure_admin_seed(db)
            ensure_seed_data(db)
    issues = settings.runtime_issues()
    if settings.app_env in {"homologation", "production"} and issues:
        raise RuntimeError("Configuração insegura/incompleta: " + " | ".join(issues))
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Gestão corporativa de processos, perfis, permissões, solicitações de acesso, "
        "aprovação e integrações resilientes com Bizagi e n8n."
    ),
    lifespan=lifespan,
    root_path=settings.root_path,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

# A ordem de registro é inversa à ordem de execução do Starlette.
# Resultado externo → interno: métricas, headers, sessão, host/HTTPS/CORS,
# CSRF, autenticação, autorização e aplicação.
app.add_middleware(AuthorizationMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CsrfMiddleware)
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", settings.csrf_header_name, "X-Request-ID"],
    )
if settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key.get_secret_value(),
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site=settings.session_same_site,
    https_only=settings.session_https_only,
)
app.add_middleware(SecurityHeadersMiddleware)
if settings.metrics_enabled:
    app.add_middleware(MetricsMiddleware)


def request_user(request: Request) -> UserAccount | None:
    return getattr(request.state, "user", None)


def actor_name(request: Request) -> str:
    user = request_user(request)
    return user.name if user else "Sistema"


def actor_email(request: Request) -> str:
    user = request_user(request)
    return user.email if user else ""


def common_context(request: Request, db: Session) -> dict:
    user = request_user(request)
    recipients = ["Todos"]
    if user:
        recipients.extend([user.name, user.email])
    notification_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.is_read.is_(False), Notification.recipient.in_(recipients)
        )
    ) or 0
    permissions = permissions_for_user(db, user)
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.app_env,
        "bizagi_enabled": settings.bizagi_enabled,
        "n8n_enabled": settings.n8n_enabled,
        "current_user": user.name if user else "Visitante",
        "current_user_email": user.email if user else "",
        "current_user_role": user.role_name if user else "",
        "current_permissions": permissions,
        "notification_count": notification_count,
        "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        "runtime_issues": settings.runtime_issues() if settings.app_env != "production" else [],
        "enable_api_docs": settings.enable_api_docs,
    }


def render(request: Request, db: Session, template: str, **context):
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={**common_context(request, db), **context},
    )


@app.get("/health/live", tags=["Sistema"])
def health_live() -> dict:
    return {"status": "ok", "version": settings.app_version}


@app.get("/health/ready", tags=["Sistema"])
def health_ready() -> dict:
    ready = database_ready() and not (
        settings.app_env in {"homologation", "production"} and settings.runtime_issues()
    )
    if not ready:
        raise HTTPException(status_code=503, detail={"database": database_ready(), "issues": settings.runtime_issues()})
    return {
        "status": "ready",
        "environment": settings.app_env,
        "database": "ok",
        "bizagi_enabled": settings.bizagi_enabled,
        "n8n_enabled": settings.n8n_enabled,
    }


@app.get("/health", tags=["Sistema"])
def health() -> dict:
    return {
        "status": "ok" if database_ready() else "degraded",
        "environment": settings.app_env,
        "version": settings.app_version,
        "bizagi_enabled": settings.bizagi_enabled,
        "n8n_enabled": settings.n8n_enabled,
    }


@app.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(default=None)) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Métricas desativadas.")
    expected = settings.metrics_bearer_token.get_secret_value()
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Token de métricas inválido.")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    if request_user(request):
        return RedirectResponse("/", status_code=303)
    token = request.cookies.get(settings.csrf_cookie_name) or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "auth_mode": settings.auth_mode,
            "csrf_token": token,
            "error": request.query_params.get("error", ""),
        },
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        secure=settings.session_https_only,
        httponly=False,
        samesite=settings.session_same_site,
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    return response


@app.post("/login", include_in_schema=False)
def local_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("/"),
    db: Session = Depends(get_db),
):
    if settings.auth_mode != "local":
        raise HTTPException(status_code=409, detail="Login local não está habilitado.")
    user = authenticate_local(db, email, password)
    if not user:
        return RedirectResponse("/login?error=Credenciais+inválidas", status_code=303)
    login_session(request, user)
    destination = next_path if next_path.startswith("/") and not next_path.startswith("//") else "/"
    return RedirectResponse(destination, status_code=303)


@app.get("/auth/oidc", include_in_schema=False)
async def oidc_login(request: Request):
    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="OIDC não habilitado.")
    register_oidc_client()
    redirect_uri = f"{settings.public_base_url.rstrip('/')}/auth/callback"
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", include_in_schema=False)
async def oidc_callback(request: Request, db: Session = Depends(get_db)):
    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="OIDC não habilitado.")
    token = await oauth.oidc.authorize_access_token(request)
    claims = token.get("userinfo")
    if not claims:
        claims = await oauth.oidc.parse_id_token(request, token)
    user = upsert_oidc_user(db, dict(claims))
    login_session(request, user)
    return RedirectResponse("/", status_code=303)


@app.get("/logout", include_in_schema=False)
def logout(request: Request):
    logout_session(request)
    if settings.oidc_logout_url:
        return RedirectResponse(settings.oidc_logout_url, status_code=303)
    return RedirectResponse("/login", status_code=303)


def redirect_with_message(path: str, message: str, kind: str = "success") -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(
        f"{path}{separator}message={quote_plus(message)}&kind={quote_plus(kind)}",
        status_code=303,
    )


def all_processes(db: Session) -> list[ProcessSpecification]:
    return list(
        db.scalars(
            select(ProcessSpecification).order_by(ProcessSpecification.updated_at.desc())
        ).all()
    )


def recent_activities(processes: list[ProcessSpecification]) -> list[dict]:
    activities: list[dict] = []
    for process in processes:
        for event in process.audit_events:
            activities.append(
                {
                    "action": event.action,
                    "label": ACTION_LABELS.get(
                        event.action, event.action.replace("_", " ").title()
                    ),
                    "actor": event.actor,
                    "process_name": process.name,
                    "process_code": process.code,
                    "process_id": process.id,
                    "created_at": event.created_at,
                }
            )
    return sorted(activities, key=lambda item: item["created_at"], reverse=True)



@app.get("/", response_class=HTMLResponse, tags=["Interface"])
def index(request: Request, db: Session = Depends(get_db)):
    processes = all_processes(db)
    return render(
        request,
        db,
        "index.html",
        processes=processes,
        recent_activities=recent_activities(processes)[:6],
        pending_processes=[p for p in processes if p.status == "pending_approval"][:5],
        profile_count=sum(len(p.profiles) for p in processes),
        synced_count=sum(1 for p in processes if p.status == "synced"),
        failed_sync_count=sum(
            1 for p in processes for job in p.integration_jobs if job.status == "failed"
        ),
    )


@app.get("/processes", response_class=HTMLResponse, tags=["Interface"])
def processes_page(request: Request, db: Session = Depends(get_db)):
    processes = all_processes(db)
    return render(
        request,
        db,
        "processes.html",
        processes=processes,
        counts=Counter(p.status for p in processes),
    )


@app.get("/profiles", response_class=HTMLResponse, tags=["Interface"])
def profiles_page(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(
        select(ProfileDefinition, ProcessSpecification)
        .join(ProcessSpecification, ProfileDefinition.process_id == ProcessSpecification.id)
        .order_by(ProfileDefinition.profile_name)
    ).all()
    return render(
        request,
        db,
        "profiles.html",
        rows=rows,
        hierarchy_counts=Counter(profile.hierarchy for profile, _ in rows),
    )


@app.get("/permissions", response_class=HTMLResponse, tags=["Interface"])
def permissions_page(request: Request, db: Session = Depends(get_db)):
    permissions = db.execute(
        select(ProfilePermission.permission_code, func.count(ProfilePermission.id))
        .group_by(ProfilePermission.permission_code)
    ).all()
    permission_counts = {code: count for code, count in permissions}
    profile_total = db.scalar(select(func.count(ProfileDefinition.id))) or 0
    process_total = db.scalar(select(func.count(ProcessSpecification.id))) or 0
    return render(
        request,
        db,
        "permissions.html",
        permission_labels=PERMISSION_LABELS,
        permission_counts=permission_counts,
        profile_total=profile_total,
        process_total=process_total,
    )


@app.get("/users", response_class=HTMLResponse, tags=["Interface"])
def users_page(request: Request, db: Session = Depends(get_db)):
    users = db.scalars(select(UserAccount).order_by(UserAccount.name)).all()
    roles = db.scalars(select(RoleDefinition).order_by(RoleDefinition.name)).all()
    units = db.scalars(select(OrganizationalUnit).order_by(OrganizationalUnit.name)).all()
    return render(request, db, "users.html", users=users, roles=roles, units=units)


@app.post("/users", tags=["Administração"])
def create_user_page(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    role_name: str = Form("Solicitante"),
    unit_name: str = Form(""),
    temporary_password: str = Form(""),
    db: Session = Depends(get_db),
):
    if db.scalar(select(UserAccount).where((UserAccount.name == name.strip()) | (UserAccount.email == email.strip()))):
        return redirect_with_message("/users", "Já existe um usuário com esse nome ou e-mail.", "error")
    db.add(UserAccount(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(temporary_password) if temporary_password else "",
        role_name=role_name.strip(),
        unit_name=unit_name.strip(),
    ))
    db.commit()
    return redirect_with_message("/users", "Usuário cadastrado com sucesso.")


@app.get("/units", response_class=HTMLResponse, tags=["Interface"])
def units_page(request: Request, db: Session = Depends(get_db)):
    units = db.scalars(select(OrganizationalUnit).order_by(OrganizationalUnit.name)).all()
    user_counts = dict(
        db.execute(
            select(UserAccount.unit_name, func.count(UserAccount.id)).group_by(UserAccount.unit_name)
        ).all()
    )
    return render(request, db, "units.html", units=units, user_counts=user_counts)


@app.post("/units", tags=["Administração"])
def create_unit_page(
    code: str = Form(...),
    name: str = Form(...),
    responsible: str = Form(""),
    db: Session = Depends(get_db),
):
    if db.scalar(select(OrganizationalUnit).where((OrganizationalUnit.code == code.strip()) | (OrganizationalUnit.name == name.strip()))):
        return redirect_with_message("/units", "Já existe uma unidade com esse código ou nome.", "error")
    db.add(OrganizationalUnit(code=code.strip().upper(), name=name.strip(), responsible=responsible.strip()))
    db.commit()
    return redirect_with_message("/units", "Unidade cadastrada com sucesso.")


@app.get("/roles", response_class=HTMLResponse, tags=["Interface"])
def roles_page(request: Request, db: Session = Depends(get_db)):
    roles = db.scalars(select(RoleDefinition).order_by(RoleDefinition.name)).all()
    user_counts = dict(db.execute(select(UserAccount.role_name, func.count(UserAccount.id)).group_by(UserAccount.role_name)).all())
    return render(request, db, "roles.html", roles=roles, user_counts=user_counts)


@app.post("/roles", tags=["Administração"])
def create_role_page(
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    if db.scalar(select(RoleDefinition).where(RoleDefinition.name == name.strip())):
        return redirect_with_message("/roles", "Já existe um papel com esse nome.", "error")
    db.add(RoleDefinition(name=name.strip(), description=description.strip(), is_system=False))
    db.commit()
    return redirect_with_message("/roles", "Papel cadastrado com sucesso.")


@app.get("/approval-flows", response_class=HTMLResponse, tags=["Interface"])
def approval_flows_page(request: Request, db: Session = Depends(get_db)):
    flows = db.scalars(select(ApprovalFlowDefinition).order_by(ApprovalFlowDefinition.id)).all()
    requests = db.scalars(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())).all()
    users = db.scalars(select(UserAccount).where(UserAccount.status == "active").order_by(UserAccount.name)).all()
    return render(
        request,
        db,
        "approval_flows.html",
        flows=flows,
        approval_requests=requests,
        users=users,
        active_flow=active_approval_flow(db),
    )


@app.post("/approval-flows", tags=["Administração"])
def save_approval_flow_page(
    name: str = Form(...),
    description: str = Form(""),
    reviewer_name: str = Form(...),
    final_approver_name: str = Form(...),
    sla_hours: int = Form(48),
    active: str | None = Form(None),
    db: Session = Depends(get_db),
):
    is_active = active == "on"
    if is_active:
        for flow in db.scalars(select(ApprovalFlowDefinition)).all():
            flow.active = False
    existing = db.scalar(select(ApprovalFlowDefinition).where(ApprovalFlowDefinition.name == name.strip()))
    if existing:
        existing.description = description.strip()
        existing.reviewer_name = reviewer_name.strip()
        existing.final_approver_name = final_approver_name.strip()
        existing.sla_hours = max(1, sla_hours)
        existing.active = is_active
    else:
        db.add(
            ApprovalFlowDefinition(
                name=name.strip(),
                description=description.strip(),
                reviewer_name=reviewer_name.strip(),
                final_approver_name=final_approver_name.strip(),
                sla_hours=max(1, sla_hours),
                active=is_active,
            )
        )
    db.commit()
    return redirect_with_message("/approval-flows", "Fluxo de aprovação salvo.")


@app.get("/settings", response_class=HTMLResponse, tags=["Interface"])
def settings_page(request: Request, db: Session = Depends(get_db)):
    settings_rows = db.scalars(select(AppSetting).order_by(AppSetting.key)).all()
    return render(request, db, "settings.html", settings_rows=settings_rows)


@app.post("/settings", tags=["Administração"])
def update_setting_page(
    key: str = Form(...),
    value: str = Form(""),
    db: Session = Depends(get_db),
):
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if not item:
        raise HTTPException(status_code=404, detail="Parâmetro não encontrado.")
    set_setting(db, key, value, item.description)
    return redirect_with_message("/settings", f"Parâmetro {key} atualizado.")


@app.get("/integrations", response_class=HTMLResponse, tags=["Interface"])
def integrations_page(request: Request, db: Session = Depends(get_db)):
    jobs = db.scalars(select(IntegrationJob).order_by(IntegrationJob.created_at.desc()).limit(30)).all()
    return render(
        request,
        db,
        "integrations.html",
        jobs=jobs,
        bizagi_missing=BizagiClient().validate_configuration(),
        n8n_missing=N8nClient().validate_configuration(),
        n8n_webhook_configured=bool(settings.n8n_webhook_url),
    )


@app.post("/integrations/n8n/test", tags=["Integrações"])
def test_n8n_page(db: Session = Depends(get_db)):
    if not settings.n8n_enabled:
        return redirect_with_message("/integrations", "Ative e configure o n8n antes de testar.", "error")
    process = db.scalar(select(ProcessSpecification).order_by(ProcessSpecification.id))
    if not process:
        return redirect_with_message("/integrations", "Cadastre um processo antes do teste.", "error")
    result = emit_n8n_event(
        db,
        process,
        "integration.test",
        {"process_id": process.id, "process_code": process.code, "message": "Teste manual do conector n8n."},
    )
    db.commit()
    return redirect_with_message(
        "/integrations",
        f"Evento de teste enfileirado com sucesso (job {result['job_id']}).",
    )


@app.post("/api/integration-jobs/{job_id}/retry", tags=["Integrações"])
def retry_integration_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(IntegrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de integração não encontrado.")
    if job.status not in {"failed", "retrying"}:
        return redirect_with_message("/integrations", "Somente jobs com falha podem ser reenfileirados.", "error")
    job.status = "pending"
    job.attempt_count = 0
    job.next_attempt_at = datetime.now(UTC)
    job.locked_at = None
    job.locked_by = ""
    job.error_message = ""
    db.add(
        AuditEvent(
            process_id=job.process_id,
            action="integration_requeued",
            actor=actor_name(request),
            actor_email=actor_email(request),
            category="integration",
            request_id=request.state.request_id,
            ip_address=request.client.host if request.client else "",
            details_json=json.dumps({"job_id": job.id, "provider": job.provider, "event": job.event_name}),
        )
    )
    db.commit()
    return redirect_with_message("/integrations", f"Job {job.id} reenfileirado com sucesso.")


@app.get("/audit-logs", response_class=HTMLResponse, tags=["Interface"])
def audit_logs_page(request: Request, db: Session = Depends(get_db)):
    events = db.execute(
        select(AuditEvent, ProcessSpecification)
        .outerjoin(ProcessSpecification, AuditEvent.process_id == ProcessSpecification.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(300)
    ).all()
    return render(request, db, "audit_logs.html", events=events, action_labels=ACTION_LABELS)


@app.get("/documentation", response_class=HTMLResponse, tags=["Interface"])
def documentation_page(request: Request, db: Session = Depends(get_db)):
    docs_dir = BASE_DIR / "docs"
    documents = sorted(p.name for p in docs_dir.iterdir() if p.is_file())
    return render(request, db, "documentation.html", documents=documents)


@app.get("/documentation/files/{filename}", tags=["Documentação"])
def documentation_file(filename: str):
    safe_name = Path(filename).name
    path = BASE_DIR / "docs" / safe_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    media_type = "application/octet-stream"
    if path.suffix.lower() == ".md":
        media_type = "text/markdown; charset=utf-8"
    elif path.suffix.lower() == ".json":
        media_type = "application/json"
    elif path.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(path.read_bytes(), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})


@app.get("/help", response_class=HTMLResponse, tags=["Interface"])
def help_page(request: Request, db: Session = Depends(get_db)):
    return render(request, db, "help.html")


@app.get("/notifications", response_class=HTMLResponse, tags=["Interface"])
def notifications_page(request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    recipients = ["Todos", user.name, user.email] if user else ["Todos"]
    notifications = db.scalars(
        select(Notification)
        .where(Notification.recipient.in_(recipients))
        .order_by(Notification.created_at.desc())
    ).all()
    return render(request, db, "notifications.html", notifications=notifications)


@app.post("/notifications/{notification_id}/read", tags=["Notificações"])
def mark_notification_read(notification_id: int, request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    notification = db.get(Notification, notification_id)
    allowed_recipients = {"Todos", user.name, user.email} if user else {"Todos"}
    if notification and notification.recipient in allowed_recipients:
        notification.is_read = True
        db.commit()
    return RedirectResponse("/notifications", status_code=303)


@app.post("/notifications/read-all", tags=["Notificações"])
def mark_all_notifications_read(request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    recipients = ["Todos", user.name, user.email] if user else ["Todos"]
    for notification in db.scalars(select(Notification).where(Notification.recipient.in_(recipients))).all():
        notification.is_read = True
    db.commit()
    return RedirectResponse("/notifications", status_code=303)


@app.get("/api/notifications", tags=["Notificações"])
def api_notifications(request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    recipients = ["Todos", user.name, user.email] if user else ["Todos"]
    rows = db.scalars(
        select(Notification)
        .where(Notification.recipient.in_(recipients))
        .order_by(Notification.created_at.desc())
        .limit(8)
    ).all()
    return {
        "unread": sum(1 for item in rows if not item.is_read),
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "category": item.category,
                "link": item.link or "/notifications",
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat(),
            }
            for item in rows
        ],
    }



@app.get("/access-requests", response_class=HTMLResponse, tags=["Acessos"])
def access_requests_page(request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    can_approve = has_permission(db, user, "access.approve")
    query = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if user and not can_approve:
        query = query.where(AccessRequest.requester_id == user.id)
    rows = list(db.scalars(query).all())
    processes = list(db.scalars(select(ProcessSpecification).order_by(ProcessSpecification.name)).all())
    roles = list(db.scalars(select(RoleDefinition).where(RoleDefinition.status == "active").order_by(RoleDefinition.name)).all())
    return render(
        request,
        db,
        "access_requests.html",
        access_requests=rows,
        processes=processes,
        roles=roles,
        system_permissions=sorted(ALL_PERMISSIONS),
        can_approve=can_approve,
    )


@app.post("/access-requests", tags=["Acessos"])
def create_access_request_page(
    request: Request,
    process_id: str = Form(""),
    requested_role: str = Form(""),
    requested_permissions: list[str] = Form(default=[]),
    justification: str = Form(...),
    db: Session = Depends(get_db),
):
    user = request_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    try:
        payload = AccessRequestCreate(
            process_id=int(process_id) if process_id else None,
            requested_role=requested_role,
            requested_permissions=requested_permissions,
            justification=justification,
        )
    except Exception as exc:
        return redirect_with_message("/access-requests", f"Dados inválidos: {exc}", "error")
    unknown_permissions = set(payload.requested_permissions) - ALL_PERMISSIONS
    if unknown_permissions:
        return redirect_with_message(
            "/access-requests",
            "Permissões desconhecidas: " + ", ".join(sorted(unknown_permissions)),
            "error",
        )
    if not payload.requested_role and not payload.requested_permissions:
        return redirect_with_message("/access-requests", "Selecione um papel ou ao menos uma permissão.", "error")
    if payload.requested_role and not db.scalar(
        select(RoleDefinition.id).where(
            RoleDefinition.name == payload.requested_role,
            RoleDefinition.status == "active",
        )
    ):
        return redirect_with_message("/access-requests", "O papel solicitado não existe ou está inativo.", "error")
    if payload.process_id and not db.get(ProcessSpecification, payload.process_id):
        return redirect_with_message("/access-requests", "O processo informado não existe.", "error")
    approver = get_setting(db, "access_request_approver", settings.approval_default_final_approver)
    item = create_access_request(
        db,
        requester=user,
        process_id=payload.process_id,
        requested_role=payload.requested_role,
        requested_permissions=payload.requested_permissions,
        justification=payload.justification,
        assigned_to=approver,
    )
    add_audit(
        db,
        payload.process_id,
        "access_requested",
        user.name,
        {"access_request_id": item.id, "role": payload.requested_role, "permissions": payload.requested_permissions},
        actor_email=user.email,
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="security",
    )
    db.commit()
    return redirect_with_message("/access-requests", "Solicitação enviada para aprovação.")


@app.post("/api/access-requests/{request_id}/approve", tags=["Acessos"])
def approve_access_request_api(
    request_id: int,
    request: Request,
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    actor = request_user(request)
    item = db.get(AccessRequest, request_id)
    if not actor or not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    try:
        approve_access_request(db, item, actor, note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        db,
        item.process_id,
        "access_approved",
        actor.name,
        {"access_request_id": item.id, "note": note},
        actor_email=actor.email,
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="security",
    )
    db.commit()
    return redirect_with_message("/access-requests", "Acesso aprovado e aplicado.")


@app.post("/api/access-requests/{request_id}/reject", tags=["Acessos"])
def reject_access_request_api(
    request_id: int,
    request: Request,
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    actor = request_user(request)
    item = db.get(AccessRequest, request_id)
    if not actor or not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    try:
        reject_access_request(db, item, actor, note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        db,
        item.process_id,
        "access_rejected",
        actor.name,
        {"access_request_id": item.id, "note": note},
        actor_email=actor.email,
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="security",
    )
    db.commit()
    return redirect_with_message("/access-requests", "Solicitação recusada.", "warning")


@app.get("/processes/{process_id}", response_class=HTMLResponse, tags=["Interface"])
def process_page(process_id: int, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    data = serialize_process(process)
    return render(
        request,
        db,
        "process.html",
        process=process,
        initial_data=data,
    )


@app.post("/api/processes", tags=["Processos"], status_code=201)
def api_create_process(payload: ProcessCreate, request: Request, db: Session = Depends(get_db)):
    user = request_user(request)
    payload = payload.model_copy(update={"actor": user.name if user else "Sistema"})
    try:
        process = create_process(db, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": "Processo criado com sucesso.", "process": serialize_process(process)}


@app.get("/api/processes/{process_id}", tags=["Processos"])
def api_get_process(process_id: int, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return serialize_process(process)


@app.put("/api/processes/{process_id}/matrix", tags=["Processos"])
def api_update_matrix(
    process_id: int,
    payload: MatrixUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    user = request_user(request)
    payload = payload.model_copy(update={"actor": user.name if user else "Sistema"})
    try:
        warnings = replace_matrix(db, process, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    updated = get_process(db, process_id)
    return {"message": "Matriz salva com sucesso.", "warnings": warnings, "process": serialize_process(updated)}


@app.post("/api/processes/{process_id}/submit", tags=["Fluxo de aprovação"])
def api_submit(process_id: int, payload: ActorInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if process.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser enviados para aprovação.")
    if current_pending_request(db, process.id):
        raise HTTPException(status_code=409, detail="Já existe uma solicitação de aprovação pendente.")
    actor = actor_name(request)
    process.status = "pending_approval"
    process.updated_by = actor
    approval = create_first_approval_request(db, process, actor)
    db.flush()
    add_audit(
        db,
        process.id,
        "submitted_for_approval",
        actor,
        {"version": process.version, "stage": approval.stage_name, "assigned_to": approval.assigned_to},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
    )
    emit_n8n_event(
        db,
        process,
        "approval.requested",
        {
            "process_id": process.id,
            "correlation_id": process.correlation_id,
            "code": process.code,
            "name": process.name,
            "version": process.version,
            "requested_by": actor,
            "assigned_to": approval.assigned_to,
            "stage": approval.stage_name,
            "url": f"{settings.public_base_url.rstrip('/')}/processes/{process.id}",
        },
    )
    db.commit()
    db.expire_all()
    return {
        "message": f"Enviado para {approval.stage_name.lower()}, responsável: {approval.assigned_to}.",
        "destination": {"stage": approval.stage_name, "assigned_to": approval.assigned_to, "queue": "/approval-flows"},
        "process": serialize_process(get_process(db, process_id)),
    }


@app.post("/api/processes/{process_id}/approve", tags=["Fluxo de aprovação"])
def api_approve(process_id: int, payload: DecisionInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if process.status != "pending_approval":
        raise HTTPException(status_code=409, detail="O processo precisa estar pendente de aprovação.")
    actor_user = request_user(request)
    actor = actor_name(request)
    approval_request = current_pending_request(db, process.id)
    if not approval_request:
        approval_request = create_first_approval_request(db, process, "Migração de versão anterior")
        db.flush()
    is_manager = has_permission(db, actor_user, "approval.manage")
    if not is_manager and approval_request.assigned_to not in {actor, actor_email(request)}:
        raise HTTPException(status_code=403, detail=f"A etapa está atribuída a {approval_request.assigned_to}.")

    complete_approval_request(approval_request, actor, "approved", payload.note)
    next_request = move_to_next_approval_stage(db, process, approval_request, actor)
    if next_request:
        add_audit(
            db,
            process.id,
            "approval_stage_completed",
            actor,
            {
                "completed_stage": approval_request.stage_name,
                "next_stage": next_request.stage_name,
                "assigned_to": next_request.assigned_to,
            },
            actor_email=actor_email(request),
            request_id=request.state.request_id,
            ip_address=request.client.host if request.client else "",
        )
        emit_n8n_event(
            db,
            process,
            "approval.stage_completed",
            {
                "process_id": process.id,
                "correlation_id": process.correlation_id,
                "code": process.code,
                "completed_stage": approval_request.stage_name,
                "next_stage": next_request.stage_name,
                "assigned_to": next_request.assigned_to,
            },
        )
        db.commit()
        db.expire_all()
        return {
            "message": f"{approval_request.stage_name} concluída. Encaminhado para {next_request.assigned_to} ({next_request.stage_name}).",
            "process": serialize_process(get_process(db, process_id)),
        }

    process.status = "approved"
    process.approved_by = actor
    process.approved_at = datetime.now(UTC)
    process.updated_by = actor
    process.bizagi_sync_status = "ready" if settings.bizagi_enabled else "not_configured"
    add_audit(
        db,
        process.id,
        "approved",
        actor,
        {"version": process.version},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
    )
    create_notification(
        db,
        approval_request.requested_by,
        f"Processo aprovado: {process.code}",
        f"{actor} concluiu a aprovação do processo “{process.name}”.",
        category="success",
        link=f"/processes/{process.id}",
    )
    emit_n8n_event(
        db,
        process,
        "approval.approved",
        {
            "process_id": process.id,
            "correlation_id": process.correlation_id,
            "code": process.code,
            "name": process.name,
            "approved_by": actor,
            "version": process.version,
        },
    )
    if settings.bizagi_enabled and settings.bizagi_auto_sync_after_approval:
        enqueue_job(
            db,
            provider="bizagi",
            event_name="bizagi.start_case",
            payload=serialize_process(process),
            process_id=process.id,
            correlation_id=process.correlation_id,
            idempotency_key=f"bizagi:start:{process.correlation_id}:v{process.version}",
        )
        process.bizagi_sync_status = "queued"
    db.commit()
    db.expire_all()
    return {"message": "Especificação aprovada e bloqueada.", "process": serialize_process(get_process(db, process_id))}


@app.post("/api/processes/{process_id}/reject", tags=["Fluxo de aprovação"])
def api_reject(process_id: int, payload: DecisionInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    approval_request = current_pending_request(db, process.id)
    if process.status != "pending_approval" or not approval_request:
        raise HTTPException(status_code=409, detail="Não há aprovação pendente para devolver.")
    actor_user = request_user(request)
    actor = actor_name(request)
    if not has_permission(db, actor_user, "approval.manage") and approval_request.assigned_to not in {actor, actor_email(request)}:
        raise HTTPException(status_code=403, detail=f"A etapa está atribuída a {approval_request.assigned_to}.")
    complete_approval_request(approval_request, actor, "rejected", payload.note)
    process.status = "draft"
    process.updated_by = actor
    add_audit(
        db,
        process.id,
        "rejected",
        actor,
        {"stage": approval_request.stage_name, "note": payload.note},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
    )
    create_notification(
        db,
        approval_request.requested_by,
        f"Ajustes solicitados: {process.code}",
        payload.note or f"{actor} devolveu o processo para ajustes.",
        category="warning",
        link=f"/processes/{process.id}",
    )
    emit_n8n_event(
        db,
        process,
        "approval.rejected",
        {"process_id": process.id, "correlation_id": process.correlation_id, "code": process.code, "rejected_by": actor, "note": payload.note},
    )
    db.commit()
    db.expire_all()
    return {"message": "Processo devolvido para ajustes.", "process": serialize_process(get_process(db, process_id))}


@app.post("/api/processes/{process_id}/reopen", tags=["Fluxo de aprovação"])
def api_reopen(process_id: int, payload: ActorInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if process.status not in {"pending_approval", "approved", "synced"}:
        raise HTTPException(status_code=409, detail="O processo já está em edição.")
    actor = actor_name(request)
    previous = process.status
    process.status = "draft"
    process.approved_by = ""
    process.approved_at = None
    process.updated_by = actor
    process.row_version += 1
    process.bizagi_sync_status = "not_configured" if not settings.bizagi_enabled else "ready"
    for approval_request in process.approval_requests:
        if approval_request.status == "pending":
            approval_request.status = "cancelled"
            approval_request.decision_by = actor
            approval_request.decided_at = datetime.now(UTC)
    add_audit(
        db,
        process.id,
        "reopened",
        actor,
        {"previous_status": previous},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
    )
    db.commit()
    db.expire_all()
    return {"message": "Especificação reaberta para edição.", "process": serialize_process(get_process(db, process_id))}


@app.get("/api/processes/{process_id}/bizagi/payload", tags=["Bizagi"])
def api_bizagi_payload(process_id: int, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    payload = serialize_process(process)
    client = BizagiClient()
    return {
        "enabled": settings.bizagi_enabled,
        "missing_configuration": client.validate_configuration(),
        "business_payload": payload,
        "bizagi_request": client.build_start_parameters(payload),
    }


@app.post("/api/processes/{process_id}/bizagi/simulate", tags=["Bizagi"])
def api_bizagi_simulate(process_id: int, payload: ActorInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if process.status != "approved":
        raise HTTPException(status_code=409, detail="A simulação exige uma versão aprovada.")
    business_payload = serialize_process(process)
    client = BizagiClient()
    request_payload = client.build_start_parameters(business_payload)
    job = IntegrationJob(
        process_id=process.id,
        provider="bizagi",
        event_name="bizagi.simulate",
        status="simulated",
        attempt_count=1,
        max_attempts=1,
        correlation_id=process.correlation_id,
        request_json=json.dumps(request_payload, ensure_ascii=False),
        response_json=json.dumps({"simulation": True, "message": "Payload validado localmente."}, ensure_ascii=False),
    )
    db.add(job)
    process.bizagi_sync_status = "simulated"
    add_audit(
        db,
        process.id,
        "bizagi_simulated",
        actor_name(request),
        {"parameters": len(request_payload["startParameters"])},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="integration",
    )
    db.commit()
    return {"message": "Simulação concluída. Nenhum dado foi enviado ao Bizagi.", "payload": request_payload}


@app.post("/api/processes/{process_id}/bizagi/sync", tags=["Bizagi"])
def api_bizagi_sync(process_id: int, payload: ActorInput, request: Request, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if process.status != "approved":
        raise HTTPException(status_code=409, detail="Somente versões aprovadas podem ser sincronizadas.")
    missing = BizagiClient().validate_configuration()
    if missing or not settings.bizagi_enabled:
        raise HTTPException(status_code=409, detail="Integração Bizagi não habilitada: " + ", ".join(missing or ["BIZAGI_ENABLED"]))
    job = enqueue_job(
        db,
        provider="bizagi",
        event_name="bizagi.start_case",
        payload=serialize_process(process),
        process_id=process.id,
        correlation_id=process.correlation_id,
        idempotency_key=f"bizagi:start:{process.correlation_id}:v{process.version}",
    )
    process.bizagi_sync_status = "queued"
    add_audit(
        db,
        process.id,
        "bizagi_queued",
        actor_name(request),
        {"job_id": job.id, "idempotency_key": job.idempotency_key},
        actor_email=actor_email(request),
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="integration",
    )
    db.commit()
    return {"message": "Sincronização enfileirada. O worker executará com retentativas automáticas.", "job_id": job.id, "status": job.status}


@app.post("/api/n8n/callback", tags=["n8n"])
async def api_n8n_callback(
    request: Request,
    timestamp: str | None = Header(default=None, alias="X-N8N-Timestamp"),
    signature: str | None = Header(default=None, alias="X-N8N-Signature"),
    event_id: str | None = Header(default=None, alias="X-Event-ID"),
    legacy_secret: str | None = Header(default=None, alias="X-N8N-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    signature_ok = verify_callback_signature(
        raw_body=raw_body,
        timestamp=timestamp or "",
        signature=signature or "",
    )
    if not signature_ok:
        legacy_ok = (
            settings.n8n_allow_legacy_secret_header
            and legacy_secret
            and secrets.compare_digest(legacy_secret, settings.n8n_webhook_secret.get_secret_value())
        )
        if not legacy_ok:
            raise HTTPException(status_code=401, detail="Assinatura HMAC do webhook inválida.")
    event_key = event_id or hashlib.sha256(raw_body).hexdigest()
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    if db.scalar(select(WebhookReceipt).where(WebhookReceipt.provider == "n8n", WebhookReceipt.event_id == event_key)):
        return {"message": "Evento já processado.", "event_id": event_key, "duplicate": True}
    try:
        payload = N8nCallbackInput.model_validate_json(raw_body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Payload inválido: {exc}") from exc
    process = get_process(db, payload.process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    db.add(WebhookReceipt(provider="n8n", event_id=event_key, payload_hash=payload_hash))
    add_audit(
        db,
        process.id,
        "n8n_callback",
        payload.actor,
        {
            "event": payload.event,
            "status": payload.status,
            "message": payload.message,
            "external_reference": payload.external_reference,
            "event_id": event_key,
        },
        request_id=request.state.request_id,
        ip_address=request.client.host if request.client else "",
        category="integration",
    )
    create_notification(
        db,
        process.responsible or "Todos",
        f"Retorno n8n: {payload.event}",
        payload.message or f"Status recebido: {payload.status}",
        category="integration",
        link=f"/processes/{process.id}",
    )
    db.commit()
    return {"message": "Callback registrado.", "process_id": process.id, "event_id": event_key}


@app.get("/api/processes/{process_id}/export/json", tags=["Exportação"])
def export_json(process_id: int, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return Response(process_to_json_bytes(process), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="perfis_permissoes_{process.code}.json"'})


@app.get("/api/processes/{process_id}/export/csv", tags=["Exportação"])
def export_csv(process_id: int, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return Response(process_to_csv_bytes(process), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="perfis_permissoes_{process.code}.csv"'})


@app.get("/api/processes/{process_id}/export/docx", tags=["Exportação"])
def export_docx(process_id: int, db: Session = Depends(get_db)):
    process = get_process(db, process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return Response(process_to_docx_bytes(process), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="especificacao_perfis_permissoes_{process.code}.docx"'})
