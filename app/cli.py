from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

from sqlalchemy import select

from app.auth import hash_password
from app.config import BASE_DIR, settings
from app.database import SessionLocal, run_migrations
from app.models import UserAccount
from app.services.admin_service import ensure_admin_seed
from app.services.process_service import ensure_seed_data


def command_check_config() -> int:
    issues = settings.runtime_issues()
    print(json.dumps({"environment": settings.app_env, "issues": issues}, ensure_ascii=False, indent=2))
    return 1 if issues else 0


def command_migrate() -> int:
    run_migrations()
    print("Migrações aplicadas com sucesso.")
    return 0


def command_seed() -> int:
    run_migrations()
    with SessionLocal() as db:
        ensure_admin_seed(db)
        ensure_seed_data(db)
    print("Dados iniciais verificados/criados.")
    return 0


def command_create_user(args: argparse.Namespace) -> int:
    run_migrations()
    with SessionLocal() as db:
        existing = db.scalar(select(UserAccount).where(UserAccount.email == args.email.lower()))
        if existing:
            print("Já existe um usuário com esse e-mail.", file=sys.stderr)
            return 2
        password = args.password or secrets.token_urlsafe(16)
        db.add(
            UserAccount(
                name=args.name,
                email=args.email.lower(),
                password_hash=hash_password(password),
                role_name=args.role,
                unit_name=args.unit,
            )
        )
        db.commit()
        print(f"Usuário criado: {args.email}")
        if not args.password:
            print(f"Senha temporária: {password}")
    return 0


def command_generate_secret(args: argparse.Namespace) -> int:
    print(secrets.token_urlsafe(args.bytes))
    return 0


def command_export_openapi(args: argparse.Namespace) -> int:
    from app.main import app

    target = Path(args.output or BASE_DIR / "docs" / "openapi.json")
    target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI salvo em {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administração do Sistema de Perfis e Permissões")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-config")
    sub.add_parser("migrate")
    sub.add_parser("seed")
    create = sub.add_parser("create-user")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--role", default="Solicitante")
    create.add_argument("--unit", default="")
    create.add_argument("--password", default="")
    secret = sub.add_parser("generate-secret")
    secret.add_argument("--bytes", type=int, default=48)
    export = sub.add_parser("export-openapi")
    export.add_argument("--output", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    handlers = {
        "check-config": lambda: command_check_config(),
        "migrate": lambda: command_migrate(),
        "seed": lambda: command_seed(),
        "create-user": lambda: command_create_user(args),
        "generate-secret": lambda: command_generate_secret(args),
        "export-openapi": lambda: command_export_openapi(args),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
