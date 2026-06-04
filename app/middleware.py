"""Middleware de autenticação JWT para endpoints protegidos."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Annotated, Callable, Optional, TypeVar

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import verify_access_token

_bearer = HTTPBearer(auto_error=False)

F = TypeVar("F", bound=Callable)


async def require_auth(
    request: Request,
    token: Annotated[Optional[str], Query()] = None,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(_bearer)
    ] = None,
) -> str:
    """Valida JWT Bearer (header ou query ?token=) e injeta phone em request.state."""
    raw_token = (credentials.credentials if credentials else None) or token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Autenticação necessária")

    phone = verify_access_token(raw_token)
    request.state.phone = phone
    return phone


AuthPhone = Annotated[str, Depends(require_auth)]


def require_auth_decorator(endpoint: F) -> F:
    """
    Decorator @require_auth — exige auth_phone como parâmetro do endpoint.
    Uso: @require_auth_decorator + def handler(..., auth_phone: AuthPhone)
    Preferir AuthPhone diretamente nos parâmetros da rota.
    """
    if inspect.iscoroutinefunction(endpoint):

        @wraps(endpoint)
        async def async_wrapper(*args, **kwargs):
            if "auth_phone" not in kwargs:
                raise HTTPException(
                    status_code=500,
                    detail="Endpoint protegido requer parâmetro auth_phone: AuthPhone",
                )
            return await endpoint(*args, **kwargs)

        return async_wrapper  # type: ignore[return-value]

    @wraps(endpoint)
    def sync_wrapper(*args, **kwargs):
        if "auth_phone" not in kwargs:
            raise HTTPException(
                status_code=500,
                detail="Endpoint protegido requer parâmetro auth_phone: AuthPhone",
            )
        return endpoint(*args, **kwargs)

    return sync_wrapper  # type: ignore[return-value]
