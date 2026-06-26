from __future__ import annotations

import re
import secrets
import uuid
from http import HTTPStatus
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth import get_session_user
from app.authorization import has_permission
from app.config import settings
from app.database import SessionLocal

PUBLIC_PATH_PREFIXES = (
    "/static/",
    "/health/",
    "/api/n8n/callback",
)
PUBLIC_EXACT_PATHS = {
    "/health",
    "/login",
    "/auth/oidc",
    "/auth/callback",
    "/logout",
    "/favicon.ico",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        with SessionLocal() as db:
            user = get_session_user(request, db)
            request.state.user = user
            request.state.db_user_id = user.id if user else None

            public = request.url.path in PUBLIC_EXACT_PATHS or request.url.path.startswith(PUBLIC_PATH_PREFIXES)
            if not public and not user:
                if request.url.path.startswith("/api/"):
                    return JSONResponse(
                        status_code=HTTPStatus.UNAUTHORIZED,
                        content={"detail": "Autenticação necessária.", "request_id": request_id},
                    )
                next_url = str(request.url.path)
                return RedirectResponse(url=f"/login?next={next_url}", status_code=303)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.authorization import required_permission_for_request

        required = required_permission_for_request(request.method.upper(), request.url.path)
        if required:
            user = getattr(request.state, "user", None)
            with SessionLocal() as db:
                process_id = _extract_process_id(request.url.path)
                allowed = has_permission(db, user, required, process_id)
            if not allowed:
                if request.url.path.startswith("/api/"):
                    return JSONResponse(
                        status_code=HTTPStatus.FORBIDDEN,
                        content={
                            "detail": f"Permissão necessária: {required}",
                            "request_id": getattr(request.state, "request_id", ""),
                        },
                    )
                return Response(
                    content=(
                        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
                        "<title>Acesso negado</title><body style='font-family:Arial;padding:40px'>"
                        "<h1>Acesso negado</h1><p>Seu papel não possui permissão para esta página.</p>"
                        "<p><a href='/access-requests'>Solicitar acesso</a> · <a href='/'>Voltar</a></p>"
                        "</body></html>"
                    ),
                    media_type="text/html",
                    status_code=HTTPStatus.FORBIDDEN,
                )
        return await call_next(request)


class CsrfMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    EXEMPT_PATHS = {"/api/n8n/callback", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cookie_name = settings.csrf_cookie_name
        token = request.cookies.get(cookie_name)
        if not token:
            token = secrets.token_urlsafe(32)

        if request.method.upper() not in self.SAFE_METHODS and request.url.path not in self.EXEMPT_PATHS:
            received = request.headers.get(settings.csrf_header_name, "")
            if not received:
                content_type = request.headers.get("content-type", "")
                if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                    body = await request.body()
                    if "application/x-www-form-urlencoded" in content_type:
                        received = parse_qs(body.decode("utf-8", errors="replace")).get("_csrf", [""])[0]
                    else:
                        match = re.search(br'name="_csrf"\r\n\r\n([^\r\n]+)', body)
                        received = match.group(1).decode("utf-8", errors="replace") if match else ""

                    sent = False
                    async def receive_again():
                        nonlocal sent
                        if sent:
                            return {"type": "http.request", "body": b"", "more_body": False}
                        sent = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    request._receive = receive_again
            if not received or not secrets.compare_digest(received, token):
                return JSONResponse(
                    status_code=HTTPStatus.FORBIDDEN,
                    content={"detail": "Token CSRF inválido ou ausente."},
                )

        response = await call_next(request)
        if request.cookies.get(cookie_name) != token:
            response.set_cookie(
                cookie_name,
                token,
                secure=settings.session_https_only,
                httponly=False,
                samesite=settings.session_same_site,
                max_age=settings.session_max_age_seconds,
                path="/",
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'",
        )
        if settings.force_https:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/api/") else "private, max-age=0")
        return response


def _extract_process_id(path: str) -> int | None:
    parts = [part for part in path.split("/") if part]
    for index, part in enumerate(parts[:-1]):
        if part == "processes":
            try:
                return int(parts[index + 1])
            except (ValueError, IndexError):
                return None
    return None
