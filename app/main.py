from __future__ import annotations

import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.access import check_access, check_job_limit, record_job
from app.company_extract import extract_company_name
from app.document_types import confirmation_message, detect_document_type
from app.graph import run_pipeline
from app.llm import ENV_PATH
from app.whatsapp import send_download_link, send_error, send_message

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


class JobRecord(BaseModel):
    id: str
    company_name: str
    document_type: str
    message: str
    status: JobStatus
    confirmation_message: str
    ppt_path: Optional[str] = None
    ppt_filename: Optional[str] = None
    qa_passed: Optional[bool] = None
    qa_issues: Optional[list[str]] = None
    error: Optional[str] = None


jobs: dict[str, dict[str, Any]] = {}


def create_job(company_name: str, doc_type: str, message: str = "", phone: str = "") -> str:
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "company_name": company_name,
        "document_type": doc_type,
        "message": message or f"{doc_type} {company_name}",
        "status": JobStatus.PENDING,
        "confirmation_message": confirmation_message(doc_type, company_name),
        "ppt_path": None,
        "ppt_filename": None,
        "qa_passed": None,
        "qa_issues": None,
        "error": None,
        "whatsapp_phone": phone,
    }
    return job_id


def _run_job(job_id: str, company_name: str, document_type: str) -> None:
    jobs[job_id]["status"] = JobStatus.RUNNING

    try:
        result = run_pipeline(job_id, company_name, document_type)
        jobs[job_id].update(
            {
                "status": JobStatus.DONE,
                "ppt_path": result.get("ppt_path"),
                "ppt_filename": result.get("ppt_filename"),
                "qa_passed": result.get("qa_passed"),
                "qa_issues": result.get("qa_issues", []),
            }
        )
    except Exception as exc:
        error_msg = str(exc)
        if any(token in error_msg.lower() for token in ("429", "quota", "rate limit")):
            error_msg = (
                "Limite de uso da API Gemini atingido. "
                "Aguarde cerca de 1 minuto e tente novamente."
            )
        jobs[job_id].update(
            {
                "status": JobStatus.ERROR,
                "error": error_msg,
            }
        )


def run_job_and_notify(
    job_id: str,
    company_name: str,
    doc_type: str,
    whatsapp_from: str,
    phone: str,
) -> None:
    _run_job(job_id, company_name, doc_type)
    job = jobs.get(job_id, {})
    notify_phone = phone or whatsapp_from

    if job.get("status") == JobStatus.DONE:
        filename = job.get("ppt_filename") or f"{company_name}_{doc_type}.pptx"
        send_download_link(notify_phone, job_id, filename)
        record_job(notify_phone)
    else:
        send_error(notify_phone, company_name)



@app.post("/jobs", response_model=JobRecord, status_code=202)
def submit_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    document_type = detect_document_type(request.message)
    company_name = extract_company_name(request.message)
    job_id = create_job(company_name, document_type, message=request.message)

    background_tasks.add_task(_run_job, job_id, company_name, document_type)

    return JobRecord(**jobs[job_id])


@app.get("/jobs/{job_id}/status", response_model=JobRecord)
def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobRecord(**jobs[job_id])


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job["status"] != JobStatus.DONE:
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


@app.post("/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
):
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    if data.get("fromMe") or data.get("isGroupMsg"):
        return {"status": "ignored"}

    if data.get("type") not in ["text", "chat", None]:
        if "text" not in data and "body" not in data:
            return {"status": "ignored"}

    phone = data.get("phone", "") or data.get("from", "")
    phone = phone.replace("whatsapp:", "").replace("+", "").strip()
    phone = phone.split("@")[0]

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

    job_id = create_job(company_name, doc_type, message=message, phone=phone)
    background_tasks.add_task(
        run_job_and_notify,
        job_id=job_id,
        company_name=company_name,
        doc_type=doc_type,
        whatsapp_from=phone,
        phone=phone,
    )
    return {"status": "processing", "job_id": job_id}


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
