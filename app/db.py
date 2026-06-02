"""Supabase client singleton."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_supabase = None


def is_supabase_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def get_supabase():
    """Retorna cliente Supabase ou None se não configurado."""
    global _supabase
    if not is_supabase_configured():
        return None
    if _supabase is None:
        from supabase import create_client

        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"],
        )
    return _supabase


class _SupabaseProxy:
    """Proxy lazy para `from app.db import supabase`."""

    def __getattr__(self, name):
        client = get_supabase()
        if client is None:
            raise RuntimeError("Supabase não configurado (SUPABASE_URL / SUPABASE_KEY)")
        return getattr(client, name)


supabase = _SupabaseProxy()
