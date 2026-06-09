"""Autenticação OTP via WhatsApp + JWT."""

from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.audit import log_action
from app.db import get_supabase
from app.log_utils import mask_phone
from app.whatsapp import send_message

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
OTP_EXPIRE_MINUTES = 5

_memory_otps: dict[str, dict] = {}


class OtpRequestBody(BaseModel):
    phone: str = Field(..., min_length=8, examples=["5511999999999"])


class OtpVerifyBody(BaseModel):
    phone: str = Field(..., min_length=8, examples=["5511999999999"])
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpSentResponse(BaseModel):
    status: str = "sent"


class OtpVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    phone: str
    expires_in: int = JWT_EXPIRE_HOURS * 3600


def normalize_phone(phone: str) -> str:
    value = phone.replace("whatsapp:", "").replace("+", "").strip()
    return value.split("@")[0]


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not secret:
        raise ValueError("JWT_SECRET_KEY não configurada")
    return secret


def create_access_token(phone: str, expires_hours: int = JWT_EXPIRE_HOURS) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "phone": normalize_phone(phone),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY não configurada")
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado") from exc

    phone = payload.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Token inválido")
    return normalize_phone(str(phone))


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _store_otp(phone: str, code: str, expires_at: datetime) -> None:
    client = get_supabase()
    if client:
        client.table("otp_codes").update({"used": True}).eq("phone", phone).eq(
            "used", False
        ).execute()
        client.table("otp_codes").insert(
            {
                "phone": phone,
                "code": code,
                "expires_at": expires_at.isoformat(),
                "used": False,
            }
        ).execute()
        return

    _memory_otps[phone] = {
        "code": code,
        "expires_at": expires_at,
        "used": False,
    }


def _validate_otp(phone: str, code: str) -> bool:
    now = datetime.now(timezone.utc)
    client = get_supabase()

    if client:
        result = (
            client.table("otp_codes")
            .select("id, expires_at, used")
            .eq("phone", phone)
            .eq("code", code)
            .eq("used", False)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        row = result.data
        if not row:
            return False

        expires_at = datetime.fromisoformat(
            str(row["expires_at"]).replace("Z", "+00:00")
        )
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return False

        client.table("otp_codes").update({"used": True}).eq("id", row["id"]).execute()
        return True

    entry = _memory_otps.get(phone)
    if not entry or entry.get("used"):
        return False
    if entry.get("code") != code:
        return False
    if entry["expires_at"] <= now:
        return False

    entry["used"] = True
    return True


@router.post("/otp/request", response_model=OtpSentResponse)
def request_otp(body: OtpRequestBody):
    phone = normalize_phone(body.phone)
    if not re.fullmatch(r"\d{8,15}", phone):
        raise HTTPException(status_code=400, detail="Número de telefone inválido")

    code = _generate_otp_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    _store_otp(phone, code, expires_at)

    send_message(phone, f"Seu código EVA: {code} (válido {OTP_EXPIRE_MINUTES} minutos)")

    log_action(
        phone,
        "otp_requested",
        resource_type="auth",
        metadata={"expires_minutes": OTP_EXPIRE_MINUTES},
    )
    print(f"[auth] OTP enviado phone={mask_phone(phone)}")

    return OtpSentResponse()


@router.post("/otp/verify", response_model=OtpVerifyResponse)
def verify_otp(body: OtpVerifyBody):
    phone = normalize_phone(body.phone)
    if not _validate_otp(phone, body.code):
        log_action(
            phone,
            "otp_verify_failed",
            resource_type="auth",
        )
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")

    token = create_access_token(phone)
    log_action(phone, "otp_verified", resource_type="auth")
    print(f"[auth] OTP verificado phone={mask_phone(phone)}")

    return OtpVerifyResponse(access_token=token, phone=phone)
