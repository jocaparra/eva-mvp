"""Configuração SQLAlchemy — Postgres (ou SQLite local para dev/testes)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.llm import ENV_PATH
from app.models.base import Base

load_dotenv(ENV_PATH)

DEFAULT_SQLITE_URL = "sqlite:///./eva_workspace.db"

_engine = None
_SessionLocal: sessionmaker | None = None


def normalize_database_url(url: str) -> str:
    """Normaliza URLs do Railway/Supabase/Heroku para SQLAlchemy + psycopg2."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg2" not in url and "+asyncpg" not in url:
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def get_database_url() -> str:
    """Retorna URL do banco; SQLite local se DATABASE_URL não estiver definida."""
    raw = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)
    if raw.startswith("sqlite"):
        return raw
    return normalize_database_url(raw)


def is_postgres_configured() -> bool:
    url = os.getenv("DATABASE_URL", "")
    return url.startswith("postgresql") or url.startswith("postgres://")


def get_engine():
    """Engine singleton."""
    global _engine, _SessionLocal
    if _engine is None:
        url = get_database_url()
        engine_kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **engine_kwargs)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager para transações."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Cria tabelas (dev/teste; produção usa Alembic)."""
    import app.models  # noqa: F401 — registra todos os modelos no metadata

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
