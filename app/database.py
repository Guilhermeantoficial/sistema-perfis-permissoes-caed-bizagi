from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
from app.config import BASE_DIR, settings


class Base(DeclarativeBase):
    pass


def build_engine() -> Engine:
    kwargs: dict = {
        "pool_pre_ping": True,
        "future": True,
    }
    if settings.database_is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )
        if settings.database_url.startswith("postgresql"):
            kwargs["connect_args"] = {
                "options": f"-c statement_timeout={settings.db_statement_timeout_ms}"
            }
    return create_engine(settings.database_url, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def database_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def run_migrations() -> None:
    alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(alembic_cfg, "head")


# Compatibilidade temporária para chamadas antigas. O schema real é controlado pelo Alembic.
def ensure_schema_compatibility() -> None:
    return None
