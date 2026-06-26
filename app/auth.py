from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import UserAccount

password_hasher = PasswordHasher()
oauth = OAuth()
_oauth_registered = False


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def register_oidc_client() -> None:
    global _oauth_registered
    if _oauth_registered or settings.auth_mode != "oidc":
        return
    oauth.register(
        name="oidc",
        server_metadata_url=settings.oidc_discovery_url,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        client_kwargs={"scope": settings.oidc_scopes},
    )
    _oauth_registered = True


def get_session_user(request: Request, db: Session) -> UserAccount | None:
    if settings.auth_mode == "disabled":
        return db.scalar(select(UserAccount).where(UserAccount.email == settings.bootstrap_admin_email))
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(UserAccount, int(user_id))
    if not user or user.status != "active":
        request.session.clear()
        return None
    return user


def authenticate_local(db: Session, email: str, password: str) -> UserAccount | None:
    normalized = email.strip().lower()
    user = db.scalar(select(UserAccount).where(UserAccount.email == normalized))
    if not user or user.status != "active" or not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return user


def resolve_role_from_claims(claims: dict[str, Any]) -> str:
    groups_raw = claims.get(settings.oidc_group_claim, [])
    if isinstance(groups_raw, str):
        groups = [groups_raw]
    else:
        groups = [str(item) for item in groups_raw or []]
    mapping = settings.oidc_group_role_map
    for group in groups:
        if group in mapping:
            return mapping[group]
    return settings.oidc_default_role


def upsert_oidc_user(db: Session, claims: dict[str, Any]) -> UserAccount:
    subject = str(claims.get(settings.oidc_subject_claim, "")).strip()
    email = str(claims.get(settings.oidc_email_claim, "")).strip().lower()
    name = str(claims.get(settings.oidc_name_claim, "") or email).strip()
    if not subject or not email:
        raise HTTPException(status_code=400, detail="O provedor OIDC não retornou subject e e-mail.")

    user = db.scalar(
        select(UserAccount).where(
            (UserAccount.external_subject == subject) | (UserAccount.email == email)
        )
    )
    if not user:
        if not settings.oidc_auto_provision:
            raise HTTPException(status_code=403, detail="Usuário ainda não provisionado no sistema.")
        user = UserAccount(
            external_subject=subject,
            email=email,
            name=name,
            role_name=resolve_role_from_claims(claims),
            status="active",
        )
        db.add(user)
    else:
        user.external_subject = subject
        user.email = email
        user.name = name
        mapped_role = resolve_role_from_claims(claims)
        if mapped_role:
            user.role_name = mapped_role
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def login_session(request: Request, user: UserAccount) -> None:
    request.session.clear()
    request.session.update(
        {
            "user_id": user.id,
            "user_email": user.email,
            "user_name": user.name,
            "role_name": user.role_name,
            "authenticated_at": datetime.now(UTC).isoformat(),
        }
    )


def logout_session(request: Request) -> None:
    request.session.clear()
