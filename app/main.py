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
from app.company_extract import extract_company_name
from app.document_types import detect_document_type
from app.graph import run_pipeline
from app.jobs_store import create_job, get_job, update_job
from app.llm import ENV_PATH
from app.log_utils import log_job_created, log_webhook_error, log_webhook_received
from app.utils.doc_cache import cleanup_expired, clear_context, get_context, get_context_meta
from app.utils.template import save_client_template
from app.whatsapp import send_download_link, send_error, send_message
from app.whatsapp_documents import handle_whatsapp_document_upload
from app.whatsapp_privacy import is_first_contact, send_privacy_welcome
from app.whatsapp_templates import handle_whatsapp_template_upload

load_dotenv(ENV_PATH)

app = FastAPI(title="EVA", description="Autonomous document generation agent")

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


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
        filename = job.get("ppt_filename") or f"{company_name}_{doc_type}.pptx"
        send_download_link(notify_phone, job_id, filename)
        record_job(notify_phone)
    else:
        send_error(notify_phone, company_name)


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


@app.get("/jobs/{job_id}/status", response_model=JobRecord)
def get_job_status(job_id: str, phone: Optional[str] = None, client_id: Optional[str] = None):
    owner = phone or client_id
    job = get_job(job_id, phone=owner) if owner else get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobRecord(**job)


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str, phone: Optional[str] = None, client_id: Optional[str] = None):
    owner = phone or client_id
    job = get_job(job_id, phone=owner) if owner else get_job(job_id)
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
