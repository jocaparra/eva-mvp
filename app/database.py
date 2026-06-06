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


def get_database_url() -> str:
    """Retorna URL do banco; SQLite local se DATABASE_URL não estiver definida."""
    return os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)


def is_postgres_configured() -> bool:
    url = os.getenv("DATABASE_URL", "")
    return url.startswith("postgresql")


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
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
