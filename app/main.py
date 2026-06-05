from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.access import check_access, check_job_limit, record_job
from app.audit import log_action
from app.auth import router as auth_router
from app.company_extract import extract_company_name
from app.document_types import detect_document_type
from app.graph import run_pipeline
from app.jobs_store import create_job, get_job, list_jobs, update_job
from app.llm import ENV_PATH
from app.log_utils import log_job_created, log_webhook_error, log_webhook_received
from app.middleware import AuthPhone
from app.utils.client_documents import process_web_document_upload
from app.utils.doc_cache import cleanup_expired, clear_context, get_context, get_context_meta
from app.utils.template import save_client_template
from app.whatsapp import send_dashboard_ready, send_download_link, send_error, send_message
from app.whatsapp_documents import handle_whatsapp_document_upload
from app.whatsapp_privacy import is_first_contact, send_privacy_welcome
from app.whatsapp_templates import handle_whatsapp_template_upload

load_dotenv(ENV_PATH)

app = FastAPI(title="EVA", description="Autonomous document generation agent")

app.include_router(auth_router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@app.get("/login")
def login_page():
    return FileResponse("frontend/login.html")


@app.get("/platform")
def platform_page():
    return FileResponse("frontend/platform.html")


@app.get("/me")
async def get_me(auth_phone: AuthPhone):
    return {"phone": auth_phone}


@app.get("/deals")
async def listar_deals(auth_phone: AuthPhone):
    from app.db import get_supabase
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=503, detail="Banco não configurado")
    firma = (
        client.table("firmas")
        .select("id")
        .eq("whatsapp", auth_phone)
        .maybe_single()
        .execute()
    )
    if not firma.data:
        return []
    res = (
        client.table("deals")
        .select("*, documentos(*)")
        .eq("firma_id", firma.data["id"])
        .order("criado_em", desc=True)
        .execute()
    )
    return res.data or []


@app.get("/deal/{deal_id}")
async def ver_deal(deal_id: str, auth_phone: AuthPhone):
    from app.db import get_supabase
    from app.supabase_ops import get_signed_url
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=503, detail="Banco não configurado")
    firma = (
        client.table("firmas")
        .select("id")
        .eq("whatsapp", auth_phone)
        .maybe_single()
        .execute()
    )
    if not firma.data:
        raise HTTPException(status_code=403, detail="Acesso negado")
    deal = (
        client.table("deals")
        .select("*")
        .eq("id", deal_id)
        .eq("firma_id", firma.data["id"])
        .maybe_single()
        .execute()
    )
    if not deal.data:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    docs = client.table("documentos").select("*").eq("deal_id", deal_id).execute()
    documentos_com_url = []
    for doc in (docs.data or []):
        try:
            url = get_signed_url(doc["storage_path"])
            documentos_com_url.append({**doc, "download_url": url})
        except Exception:
            documentos_com_url.append(doc)
    return {"deal": deal.data, "documentos": documentos_com_url}


@app.get("/deal/{deal_id}/download/{doc_id}")
async def download_documento(
    deal_id: str,
    doc_id: str,
    request: Request,
    token: Optional[str] = None,
):
    from app.auth import verify_access_token
    from app.db import get_supabase
    from fastapi.responses import RedirectResponse
    auth_header = request.headers.get("Authorization", "")
    raw_token = token or (auth_header.replace("Bearer ", "") if auth_header else None)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Token necessário")
    phone = verify_access_token(raw_token)
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=503, detail="Banco não configurado")
    firma = (
        client.table("firmas")
        .select("id")
        .eq("whatsapp", phone)
        .maybe_single()
        .execute()
    )
    if not firma.data:
        raise HTTPException(status_code=403, detail="Acesso negado")
    deal = (
        client.table("deals")
        .select("id")
        .eq("id", deal_id)
        .eq("firma_id", firma.data["id"])
        .maybe_single()
        .execute()
    )
    if not deal.data:
        raise HTTPException(status_code=403, detail="Deal não encontrado")
    doc = (
        client.table("documentos")
        .select("storage_path, tipo")
        .eq("id", doc_id)
        .eq("deal_id", deal_id)
        .maybe_single()
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    signed = client.storage.from_("documentos").create_signed_url(
        doc.data["storage_path"], 3600
    )
    return RedirectResponse(url=signed["signedURL"])


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(
        ...,
        min_length=1,
        alias="company_name",
        examples=["Gerar CIM da Nubank"],
    )
    client_id: str = Field(default="default", examples=["fundo_xyz"])


class WebJobRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["Valuation da Apple"])


class UploadProcessedResponse(BaseModel):
    status: str = "processed"
    context_available: bool = True
    expires_in: str = "30min"


class JobRecord(BaseModel):
    id: str
    company_name: str
    document_type: str
    client_id: str = "default"
    status: JobStatus
    confirmation_message: str
    ppt_path: Optional[str] = None
    ppt_filename: Optional[str] = None
    qa_passed: Optional[bool] = None
    qa_issues: Optional[list[str]] = None
    error: Optional[str] = None


def _run_job(
    job_id: str,
    company_name: str,
    document_type: str,
    client_id: str = "default",
) -> None:
    job = get_job(job_id)
    phone = (job or {}).get("phone", client_id)

    update_job(job_id, status=JobStatus.RUNNING.value)

    client_context = get_context(client_id) or get_context(phone) or ""
    context_meta = get_context_meta(client_id) or get_context_meta(phone)
    if client_context:
        log_action(
            phone,
            "document_context_used",
            resource_type="job",
            resource_id=job_id,
            metadata={"doc_type": (context_meta or {}).get("doc_type")},
        )

    try:
        result = run_pipeline(
            job_id,
            company_name,
            document_type,
            client_id,
            client_context=client_context,
        )
        update_job(
            job_id,
            status=JobStatus.DONE.value,
            ppt_path=result.get("ppt_path"),
            ppt_filename=result.get("ppt_filename"),
            qa_passed=result.get("qa_passed"),
            qa_issues=result.get("qa_issues", []),
        )
        log_action(
            phone,
            "job_completed",
            resource_type="job",
            resource_id=job_id,
            metadata={"qa_passed": result.get("qa_passed")},
        )
    except Exception as exc:
        error_msg = str(exc)
        if any(token in error_msg.lower() for token in ("429", "quota", "rate limit")):
            error_msg = (
                "Limite de uso da API Gemini atingido. "
                "Aguarde cerca de 1 minuto e tente novamente."
            )
        update_job(job_id, status=JobStatus.ERROR.value, error=error_msg)
        log_action(
            phone,
            "job_error",
            resource_type="job",
            resource_id=job_id,
            metadata={"error": error_msg},
        )
    finally:
        clear_context(phone)
        if client_id != phone:
            clear_context(client_id)


def run_job_and_notify(
    job_id: str,
    company_name: str,
    doc_type: str,
    whatsapp_from: str,
    phone: str,
) -> None:
    job = get_job(job_id) or {}
    notify_phone = phone or whatsapp_from
    client_id = job.get("client_id", notify_phone)

    _run_job(job_id, company_name, doc_type, client_id)
    job = get_job(job_id) or {}

    if job.get("status") == JobStatus.DONE.value:
        ppt_path = job.get("ppt_path")
        try:
            from app.supabase_ops import get_or_create_firma, criar_deal, salvar_documento
            from app.whatsapp import send_platform_link
            firma_id = get_or_create_firma(notify_phone)
            deal_id  = criar_deal(firma_id, company_name)
            salvar_documento(deal_id, firma_id, doc_type, ppt_path)
            send_platform_link(notify_phone, deal_id, company_name)
        except Exception as e:
            print(f"[storage] Falha ao salvar no Supabase: {e}")
            filename = job.get("ppt_filename") or f"{company_name}_{doc_type}.pptx"
            send_download_link(notify_phone, job_id, filename)
        record_job(notify_phone)
    else:
        send_error(notify_phone, company_name)


def run_web_job_and_notify(
    job_id: str,
    company_name: str,
    doc_type: str,
    phone: str,
) -> None:
    _run_job(job_id, company_name, doc_type, phone)
    job = get_job(job_id) or {}

    if job.get("status") == JobStatus.DONE.value:
        send_dashboard_ready(phone)
        record_job(phone)
    else:
        send_error(phone, company_name)


@app.post("/jobs", response_model=JobRecord, status_code=202)
def submit_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    document_type = detect_document_type(request.message)
    company_name = extract_company_name(request.message)
    client_id = request.client_id or "default"
    job_id = create_job(
        company_name,
        document_type,
        client_id=client_id,
    )

    background_tasks.add_task(
        _run_job, job_id, company_name, document_type, client_id
    )

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job")
    return JobRecord(**job)


@app.post("/jobs/web", response_model=JobRecord, status_code=202)
async def submit_web_job(
    request: WebJobRequest,
    background_tasks: BackgroundTasks,
    auth_phone: AuthPhone,
):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    document_type = detect_document_type(message)
    company_name = extract_company_name(message)
    if not company_name or len(company_name) < 2:
        raise HTTPException(status_code=400, detail="Nome da empresa não identificado.")

    if not await check_access(auth_phone):
        raise HTTPException(status_code=403, detail="Assinatura ativa necessária.")

    if not await check_job_limit(auth_phone):
        raise HTTPException(status_code=429, detail="Limite mensal de documentos atingido.")

    job_id = create_job(
        company_name,
        document_type,
        phone=auth_phone,
        client_id=auth_phone,
    )
    log_job_created(auth_phone, document_type, job_id)

    background_tasks.add_task(
        run_web_job_and_notify,
        job_id=job_id,
        company_name=company_name,
        doc_type=document_type,
        phone=auth_phone,
    )

    job = get_job(job_id, phone=auth_phone)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job")
    return JobRecord(**job)


@app.post("/templates/{client_id}/upload")
async def upload_template(client_id: str, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(
            status_code=400,
            detail="Envie um arquivo .pptx válido.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    try:
        storage_path = save_client_template(client_id, content, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "ok",
        "client_id": client_id,
        "path": storage_path,
        "filename": file.filename,
    }


@app.post("/upload", response_model=UploadProcessedResponse)
async def upload_document(auth_phone: AuthPhone, file: UploadFile = File(...)):
    """Upload efêmero de documento para contexto de análise (JWT obrigatório)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo ausente.")

    content = await file.read()
    mime_type = file.content_type or ""

    try:
        result = process_web_document_upload(
            auth_phone,
            content,
            file.filename,
            mime_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Falha ao processar documento.") from exc
    finally:
        del content

    return UploadProcessedResponse(**result)


@app.post("/templates/upload")
async def upload_template_authenticated(
    auth_phone: AuthPhone,
    file: UploadFile = File(...),
):
    """Upload de template .pptx — requer JWT (phone = client_id)."""
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(
            status_code=400,
            detail="Envie um arquivo .pptx válido.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    try:
        storage_path = save_client_template(auth_phone, content, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "ok",
        "client_id": auth_phone,
        "path": storage_path,
        "filename": file.filename,
    }


@app.get("/jobs", response_model=list[JobRecord])
def list_user_jobs(auth_phone: AuthPhone):
    jobs = list_jobs(auth_phone)
    return [JobRecord(**job) for job in jobs]


@app.get("/jobs/{job_id}/status", response_model=JobRecord)
def get_job_status(job_id: str, phone: Optional[str] = None, client_id: Optional[str] = None):
    owner = phone or client_id
    job = get_job(job_id, phone=owner) if owner else get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobRecord(**job)


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str, auth_phone: AuthPhone):
    job = get_job(job_id, phone=auth_phone)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != JobStatus.DONE.value:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not ready for download (status: {job['status']})",
        )

    ppt_path = job.get("ppt_path")
    if not ppt_path or not Path(ppt_path).exists():
        raise HTTPException(status_code=404, detail="PPT file not found")

    filename = job.get("ppt_filename") or f"{job['company_name']}_{job['document_type']}.pptx"

    return FileResponse(
        path=ppt_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@app.on_event("startup")
def _startup_doc_cache_cleanup():
    cleanup_expired()


@app.post("/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
):
    try:
        cleanup_expired()
        data = await request.json()

        if data.get("fromMe") or data.get("isGroupMsg"):
            return {"status": "ignored"}

        phone = data.get("phone", "") or data.get("from", "")
        phone = phone.replace("whatsapp:", "").replace("+", "").strip()
        phone = phone.split("@")[0]

        log_webhook_received(phone, data.get("type"))

        if not phone:
            return {"status": "ignored"}

        if is_first_contact(phone):
            send_privacy_welcome(phone)

        template_result = handle_whatsapp_template_upload(data, phone)
        if template_result:
            return template_result

        document_result = handle_whatsapp_document_upload(data, phone)
        if document_result:
            return document_result

        if data.get("type") not in ["text", "chat", None, "ReceivedCallback"]:
            if "text" not in data and "body" not in data and "document" not in data:
                return {"status": "ignored"}

        message = (
            data.get("text", {}).get("message", "")
            if isinstance(data.get("text"), dict)
            else ""
        ) or data.get("body", "") or data.get("message", "") or ""
        message = message.strip()

        if not phone or not message:
            return {"status": "ignored"}

        msg_lower = message.lower()

        if any(
            w in msg_lower
            for w in [
                "assinar",
                "plano",
                "preço",
                "preco",
                "valor",
                "quanto custa",
                "quero acessar",
            ]
        ):
            from app.payments import create_checkout_session

            link = create_checkout_session(phone)
            send_message(
                phone,
                "💳 *Plano EVA*\n\n"
                "✅ 30 documentos por mês\n"
                "✅ CIM, Valuation e Due Diligence\n"
                "✅ Entrega direto no WhatsApp\n\n"
                f"👉 Assine aqui:\n{link}\n\n"
                "_Acesso ativado automaticamente após o pagamento._",
            )
            return {"status": "checkout_sent"}

        if any(w in msg_lower for w in ["ajuda", "help", "como usar", "comandos"]):
            send_message(
                phone,
                "🤖 *EVA — Comandos disponíveis*\n\n"
                "📄 *CIM:*\n_CIM da [empresa]_\n\n"
                "💰 *Valuation:*\n_Valuation da [empresa]_\n\n"
                "🔍 *Due Diligence:*\n_Due diligence da [empresa]_\n\n"
                "💳 *Assinar:*\n_assinar_\n\n"
                "Exemplo: _Valuation da Apple_",
            )
            return {"status": "help_sent"}

        if os.getenv("WHATSAPP_OPEN_ACCESS", "false").lower() == "true":
            has_access = True
        else:
            has_access = await check_access(phone)

        if not has_access:
            from app.payments import create_checkout_session

            link = create_checkout_session(phone)
            send_message(
                phone,
                "⛔ Você não tem acesso à EVA.\n\n"
                "Para assinar:\n"
                f"👉 {link}\n\n"
                "_30 documentos/mês. Ativação imediata._",
            )
            return {"status": "blocked"}

        within_limit = await check_job_limit(phone)
        if not within_limit:
            send_message(
                phone,
                "⚠️ Você atingiu o limite de *30 documentos* este mês.\n\n"
                "Seu acesso renova automaticamente no próximo ciclo.",
            )
            return {"status": "limit_reached"}

        doc_type = detect_document_type(message)
        company_name = extract_company_name(message)

        if not company_name or len(company_name) < 2:
            send_message(
                phone,
                "🤔 Não entendi o nome da empresa.\n\n"
                "Tente assim:\n"
                "• _Valuation da Apple_\n"
                "• _CIM da Magazine Luiza_\n"
                "• _Due diligence da Nubank_",
            )
            return {"status": "unclear"}

        labels = {
            "CIM": "CIM",
            "VALUATION": "Valuation",
            "DUE_DILIGENCE": "Due Diligence",
        }
        send_message(
            phone,
            f"⏳ Gerando *{labels[doc_type]}* de *{company_name}*...\n\n"
            f"Aguarde 2 a 5 minutos.\n"
            f"Você receberá o link de download aqui.",
        )

        job_id = create_job(
            company_name,
            doc_type,
            phone=phone,
            client_id=phone,
        )
        log_job_created(phone, doc_type, job_id)
        background_tasks.add_task(
            run_job_and_notify,
            job_id=job_id,
            company_name=company_name,
            doc_type=doc_type,
            whatsapp_from=phone,
            phone=phone,
        )
        return {"status": "processing", "job_id": job_id}

    except Exception as e:
        log_webhook_error(e)
        return {"status": "error", "detail": type(e).__name__}


@app.post("/whatsapp/status")
async def whatsapp_status(request: Request):
    return {"status": "ok"}


@app.post("/whatsapp/connect")
async def whatsapp_connect(request: Request):
    return {"status": "ok"}


@app.post("/whatsapp/disconnect")
async def whatsapp_disconnect(request: Request):
    print("WhatsApp desconectado — reconectar no painel Z-API")
    return {"status": "ok"}
