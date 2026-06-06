from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.access import check_access, check_job_limit, record_job
from app.audit import log_action
from app.auth import router as auth_router
from app.company_extract import extract_company_name
from app.database import get_db, init_db, session_scope
from app.document_types import detect_document_type
from app.graph import run_pipeline
from app.jobs_store import create_job, get_job, list_jobs, update_job
from app.llm import ENV_PATH
from app.log_utils import log_job_created, log_webhook_error, log_webhook_received
from app.middleware import AuthPhone
from app.repositories.deal_workspace import (
    DealAccessDeniedError,
    DealNotFoundError,
    create_deal,
    get_deal_for_owner,
    list_deals_for_owner,
    to_deal_state,
)
from app.schemas.deal_workspace import (
    ApproveArtifactRequest,
    ApproveArtifactResponse,
    ArtifactReviewResponse,
    CreateDealRequest,
    DealListItemResponse,
    DealWorkspaceResponse,
    WorkspaceArtifactResponse,
    WorkspaceDocumentResponse,
)
from app.services.artifact_review import build_artifact_review
from app.repositories.workspace_artifact import (
    AlreadyApprovedError,
    ApprovalBlockedError,
    ArtifactNotFoundError,
    approve_artifact,
    get_artifact_for_owner,
    upsert_artifact_from_pipeline,
)
from app.repositories.conversation import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    add_message,
    create_conversation,
    delete_conversation,
    ensure_deal_for_conversation,
    get_conversation_for_owner,
    list_conversations,
    update_conversation_title,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)
from app.services.document_ingestion import ingest_deal_document
from app.services.artifact_persistence import persist_pipeline_artifact
from app.services.conversation_jobs import finalize_conversation_job, prepare_conversation_job
from app.storage.artifact_storage import get_artifact_storage, guess_content_type
from app.utils.doc_cache import cleanup_expired, clear_context, get_context, get_context_meta
from app.utils.template import save_client_template
from app.whatsapp import send_dashboard_ready, send_download_link, send_error, send_message
from app.whatsapp_documents import handle_whatsapp_document_upload
from app.whatsapp_privacy import is_first_contact, send_privacy_welcome
from app.whatsapp_templates import handle_whatsapp_template_upload

load_dotenv(ENV_PATH)

app = FastAPI(title="EVA", description="Autonomous document generation agent")


@app.get("/health")
def health_check():
    """Healthcheck para Railway/load balancers."""
    return {"status": "ok"}


def _artifact_type_label(artifact_type: str) -> str:
    mapping = {"cim_pptx": "CIM", "memo_docx": "MEMO", "CIM": "CIM", "VALUATION": "VALUATION"}
    return mapping.get(artifact_type, artifact_type.upper())


def _artifact_download_media_type(artifact_type: str, file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".docx" or "memo" in artifact_type.lower():
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _artifact_download_response(artifact):
    """Monta resposta HTTP para download de um WorkspaceArtifact."""
    if not artifact.file_path:
        raise HTTPException(status_code=404, detail="Arquivo não disponível")
    filename = artifact.file_path.split("/")[-1]
    media_type = _artifact_download_media_type(artifact.artifact_type, filename)
    storage = get_artifact_storage()
    if not storage.exists(artifact.file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no storage")
    return storage.build_download_response(
        artifact.file_path,
        filename=filename,
        media_type=media_type,
    )


def _to_deal_list_item(deal) -> DealListItemResponse:
    docs = [WorkspaceDocumentResponse.model_validate(d) for d in (deal.documents or [])]
    artifacts = [WorkspaceArtifactResponse.model_validate(a) for a in (deal.artifacts or [])]
    ready = any(
        a.file_path and a.status in ("ready", "approved", "needs_review")
        for a in artifacts
    )
    doc_type = _artifact_type_label(artifacts[0].artifact_type) if artifacts else "CIM"
    return DealListItemResponse(
        id=deal.id,
        deal_id=deal.id,
        company_name=deal.company_name,
        nome=deal.company_name,
        status=deal.status,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        criado_em=deal.created_at,
        document_count=len(docs),
        artifact_count=len(artifacts),
        has_ready_artifact=ready,
        document_type=doc_type,
        documentos=docs,
        artifacts=artifacts,
    )


def _legacy_deal_detail(deal) -> dict:
    """Formato compatível com GET /deal/{id} legado + dados SQLAlchemy."""
    documentos = []
    for doc in deal.documents or []:
        documentos.append(
            {
                "id": str(doc.id),
                "source_file": doc.source_file,
                "tipo": "data_room",
                "nome": doc.source_file,
                "status": doc.status,
                "criado_em": doc.created_at.isoformat(),
            }
        )
    for art in deal.artifacts or []:
        if art.file_path:
            documentos.append(
                {
                    "id": str(art.id),
                    "source_file": art.file_path.split("/")[-1],
                    "tipo": art.artifact_type,
                    "status": art.status,
                    "criado_em": art.created_at.isoformat(),
                    "artifact_id": str(art.id),
                    "qa_passed": art.qa_passed,
                    "approved": art.approved,
                }
            )
    return {
        "deal": {
            "id": str(deal.id),
            "deal_id": str(deal.id),
            "company_name": deal.company_name,
            "nome": deal.company_name,
            "status": deal.status,
            "criado_em": deal.created_at.isoformat(),
            "updated_at": deal.updated_at.isoformat(),
        },
        "documentos": documentos,
        "documents": [WorkspaceDocumentResponse.model_validate(d).model_dump(mode="json") for d in deal.documents or []],
        "artifacts": [WorkspaceArtifactResponse.model_validate(a).model_dump(mode="json") for a in deal.artifacts or []],
    }


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
    from app.db import get_supabase

    return {
        "phone": auth_phone,
        "storage_enabled": get_supabase() is not None,
    }


@app.post("/files/upload")
async def upload_arquivo(auth_phone: AuthPhone, file: UploadFile = File(...)):
    """Upload para Supabase Storage (arquivos de referência do usuário)."""
    from app.db import get_supabase
    from app.supabase_ops import get_or_create_firma

    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")
    client = get_supabase()
    if not client:
        raise HTTPException(
            status_code=409,
            detail="Armazenamento de arquivos não configurado.",
        )
    content = await file.read()
    firma_id = get_or_create_firma(auth_phone)
    storage_path = f"{firma_id}/files/{file.filename}"
    try:
        client.storage.from_("arquivos").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            client.storage.from_("arquivos").remove([storage_path])
            client.storage.from_("arquivos").upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type or "application/octet-stream"},
            )
        else:
            raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "ok", "filename": file.filename, "path": storage_path}


@app.get("/files")
async def listar_arquivos(auth_phone: AuthPhone):
    from app.db import get_supabase
    from app.supabase_ops import get_or_create_firma

    client = get_supabase()
    if not client:
        return {
            "storage_enabled": False,
            "files": [],
            "message": "Armazenamento de arquivos não configurado.",
        }
    firma_id = get_or_create_firma(auth_phone)
    try:
        files = client.storage.from_("arquivos").list(f"{firma_id}/files")
        result = []
        for f in (files or []):
            signed = client.storage.from_("arquivos").create_signed_url(
                f"{firma_id}/files/{f['name']}", 3600
            )
            size_kb = round(f.get("metadata", {}).get("size", 0) / 1024, 1)
            result.append({
                "name": f["name"],
                "url": signed["signedURL"],
                "size": f"{size_kb} KB" if size_kb else "",
            })
        return {"storage_enabled": True, "files": result}
    except Exception:
        return {"storage_enabled": True, "files": []}


@app.post("/auth/dev-login")
async def dev_login(request: Request):
    from app.auth import create_access_token, normalize_phone
    body = await request.json()
    phone = normalize_phone(str(body.get("phone", "")))
    if not phone:
        raise HTTPException(status_code=400, detail="Número inválido")
    token = create_access_token(phone)
    return {"access_token": token, "phone": phone, "token_type": "bearer"}


@app.post("/deals", response_model=DealWorkspaceResponse, status_code=201)
def criar_deal_workspace(
    request: CreateDealRequest,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Cria um deal workspace persistente (Postgres/SQLAlchemy)."""
    deal = create_deal(db, company_name=request.company_name, owner_phone=auth_phone)
    return to_deal_state(deal)


@app.post("/deals/{deal_id}/documents", response_model=WorkspaceDocumentResponse, status_code=201)
async def upload_deal_document(
    deal_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """Upload de documento do data room → parse → chunk → embed → index."""
    from uuid import UUID

    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")

    try:
        deal_uuid = UUID(deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID de deal inválido") from exc

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    try:
        document, _chunk_count = ingest_deal_document(
            db,
            deal_id=deal_uuid,
            owner_phone=auth_phone,
            filename=file.filename,
            content=content,
            mime_type=file.content_type or "",
        )
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return document


@app.get("/deals/{deal_id}", response_model=DealWorkspaceResponse)
def obter_deal_workspace(
    deal_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Retorna deal workspace com documentos e artefatos."""
    from uuid import UUID

    try:
        deal_uuid = UUID(deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID de deal inválido") from exc

    try:
        deal = get_deal_for_owner(db, deal_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")

    return to_deal_state(deal)


def _conversation_http_errors(exc: Exception) -> None:
    if isinstance(exc, ConversationNotFoundError):
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if isinstance(exc, ConversationAccessDeniedError):
        raise HTTPException(status_code=403, detail="Acesso negado")
    raise exc


@app.post("/conversations", response_model=ConversationSummary, status_code=201)
def criar_conversa(
    request: ConversationCreate,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    title = (request.title or "").strip() or "Nova conversa"
    conv = create_conversation(db, owner_phone=auth_phone, title=title)
    return ConversationSummary.model_validate(conv)


@app.get("/conversations", response_model=List[ConversationSummary])
def listar_conversas(auth_phone: AuthPhone, db: Session = Depends(get_db)):
    convs = list_conversations(db, auth_phone)
    return [ConversationSummary.model_validate(c) for c in convs]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def obter_conversa(
    conversation_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc
    try:
        conv = get_conversation_for_owner(db, conv_uuid, auth_phone)
    except (ConversationNotFoundError, ConversationAccessDeniedError) as exc:
        _conversation_http_errors(exc)
    return ConversationDetail.model_validate(conv)


@app.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
def anexar_mensagem(
    conversation_id: str,
    request: MessageCreate,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    from uuid import UUID

    if request.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role deve ser user ou assistant")
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc
    try:
        msg = add_message(
            db,
            conversation_id=conv_uuid,
            owner_phone=auth_phone,
            role=request.role,
            content=request.content.strip(),
            job_id=request.job_id,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError) as exc:
        _conversation_http_errors(exc)
    return MessageResponse.model_validate(msg)


@app.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def renomear_conversa(
    conversation_id: str,
    request: ConversationUpdate,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc
    try:
        conv = update_conversation_title(db, conv_uuid, auth_phone, request.title)
    except (ConversationNotFoundError, ConversationAccessDeniedError) as exc:
        _conversation_http_errors(exc)
    return ConversationSummary.model_validate(conv)


@app.delete("/conversations/{conversation_id}", status_code=204)
def apagar_conversa(
    conversation_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc
    try:
        delete_conversation(db, conv_uuid, auth_phone)
    except (ConversationNotFoundError, ConversationAccessDeniedError) as exc:
        _conversation_http_errors(exc)


@app.post("/conversations/{conversation_id}/documents")
async def upload_conversation_document(
    conversation_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """Ingestão no deal da conversa — cria deal se necessário."""
    from uuid import UUID

    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    try:
        conv = get_conversation_for_owner(db, conv_uuid, auth_phone)
        company = conv.title if conv.title != "Nova conversa" else "Data room"
        deal_uuid = ensure_deal_for_conversation(db, conv_uuid, auth_phone, company)
        document, chunk_count = ingest_deal_document(
            db,
            deal_id=deal_uuid,
            owner_phone=auth_phone,
            filename=file.filename,
            content=content,
            mime_type=file.content_type or "",
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    except ConversationAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "document": WorkspaceDocumentResponse.model_validate(document),
        "chunk_count": chunk_count,
        "deal_id": str(deal_uuid),
    }


@app.get("/deals/{deal_id}/artifacts/{artifact_id}", response_model=ArtifactReviewResponse)
def obter_artifact_review(
    deal_id: str,
    artifact_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Revisão humana — audit por campo (status, delta, citação, chunks buscados)."""
    from uuid import UUID

    try:
        deal_uuid = UUID(deal_id)
        artifact_uuid = UUID(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc

    try:
        artifact = get_artifact_for_owner(db, deal_uuid, artifact_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except ArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado")

    return build_artifact_review(db, artifact)


@app.post(
    "/deals/{deal_id}/artifacts/{artifact_id}/approve",
    response_model=ApproveArtifactResponse,
    status_code=201,
)
def aprovar_artifact(
    deal_id: str,
    artifact_id: str,
    request: ApproveArtifactRequest,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Aprovação imutável; override com justificativa quando há issues bloqueantes."""
    from uuid import UUID

    from app.schemas.deal_workspace import ArtifactApprovalResponse, WorkspaceArtifactResponse

    try:
        deal_uuid = UUID(deal_id)
        artifact_uuid = UUID(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc

    try:
        approval = approve_artifact(
            db,
            deal_id=deal_uuid,
            artifact_id=artifact_uuid,
            owner_phone=auth_phone,
            override_reason=request.override_reason,
        )
        artifact = get_artifact_for_owner(db, deal_uuid, artifact_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except ArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado")
    except AlreadyApprovedError:
        raise HTTPException(status_code=409, detail="Artefato já aprovado nesta versão")
    except ApprovalBlockedError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "blocking_issues": exc.blocking_issues},
        )

    log_action(
        auth_phone,
        "artifact_approved",
        resource_type="artifact",
        resource_id=str(artifact_uuid),
        metadata={
            "deal_id": deal_id,
            "version": artifact.version,
            "override": approval.override,
            "had_blocking_issues": approval.had_blocking_issues,
        },
    )

    return ApproveArtifactResponse(
        approval=ArtifactApprovalResponse.model_validate(approval),
        artifact=WorkspaceArtifactResponse.model_validate(artifact),
    )


@app.get("/deals/{deal_id}/artifacts/{artifact_id}/download")
def download_artifact(
    deal_id: str,
    artifact_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Download autenticado do artefato gerado via object storage."""
    from uuid import UUID

    try:
        deal_uuid = UUID(deal_id)
        artifact_uuid = UUID(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc

    try:
        artifact = get_artifact_for_owner(db, deal_uuid, artifact_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    except ArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado")

    if not artifact.file_path:
        raise HTTPException(status_code=404, detail="Arquivo não disponível")

    return _artifact_download_response(artifact)


@app.get("/deals", response_model=List[DealListItemResponse])
def listar_deals(auth_phone: AuthPhone, db: Session = Depends(get_db)):
    """Lista deals do workspace SQLAlchemy (sem Supabase)."""
    deals = list_deals_for_owner(db, auth_phone)
    return [_to_deal_list_item(deal) for deal in deals]


@app.get("/deal/{deal_id}")
def ver_deal(deal_id: str, auth_phone: AuthPhone, db: Session = Depends(get_db)):
    """Detalhe do deal — documentos ingeridos + artefatos gerados (SQLAlchemy)."""
    from uuid import UUID

    try:
        deal_uuid = UUID(deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID de deal inválido") from exc
    try:
        deal = get_deal_for_owner(db, deal_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return _legacy_deal_detail(deal)


@app.get("/deal/{deal_id}/download/{doc_id}")
def download_documento(
    deal_id: str,
    doc_id: str,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Download legado — data room (WorkspaceDocument) ou artefato gerado (SQLAlchemy)."""
    from uuid import UUID

    from app.models.deal_workspace import WorkspaceDocument

    try:
        deal_uuid = UUID(deal_id)
        resource_uuid = UUID(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc

    try:
        get_deal_for_owner(db, deal_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")

    document = (
        db.query(WorkspaceDocument)
        .filter(
            WorkspaceDocument.id == resource_uuid,
            WorkspaceDocument.deal_id == deal_uuid,
        )
        .one_or_none()
    )
    if document and document.storage_path:
        path = Path(document.storage_path)
        if path.is_file():
            media_type = document.mime_type or guess_content_type(document.source_file)
            return FileResponse(
                path=str(path),
                filename=document.source_file,
                media_type=media_type,
            )

    try:
        artifact = get_artifact_for_owner(db, deal_uuid, resource_uuid, auth_phone)
    except ArtifactNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    return _artifact_download_response(artifact)


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
    conversation_id: Optional[str] = None


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
    conversation_id: Optional[str] = None
    deal_id: Optional[str] = None


class DealGenerateRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["Gerar CIM da Empresa Alvo"])


@app.post("/deals/{deal_id}/generate", response_model=JobRecord, status_code=202)
async def gerar_artifact_deal(
    deal_id: str,
    request: DealGenerateRequest,
    background_tasks: BackgroundTasks,
    auth_phone: AuthPhone,
    db: Session = Depends(get_db),
):
    """Dispara geração de artefato vinculada ao deal (persiste ao concluir)."""
    from uuid import UUID

    try:
        deal_uuid = UUID(deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID de deal inválido") from exc

    try:
        deal = get_deal_for_owner(db, deal_uuid, auth_phone)
    except DealNotFoundError:
        raise HTTPException(status_code=404, detail="Deal não encontrado")
    except DealAccessDeniedError:
        raise HTTPException(status_code=403, detail="Acesso negado")

    message = request.message.strip()
    document_type = detect_document_type(message)
    company_name = deal.company_name

    job_id = create_job(
        company_name,
        document_type,
        phone=auth_phone,
        client_id=auth_phone,
        deal_id=deal_id,
        db=db,
    )

    background_tasks.add_task(_run_job, job_id, company_name, document_type, auth_phone)

    job = get_job(job_id, phone=auth_phone, db=db)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job")
    return JobRecord(**job)


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
            deal_id=(job or {}).get("deal_id") or "",
        )
        deal_id = (job or {}).get("deal_id") or ""
        result = persist_pipeline_artifact(result, deal_id=deal_id, job_id=job_id)
        update_job(
            job_id,
            status=JobStatus.DONE.value,
            ppt_path=result.get("ppt_path"),
            ppt_filename=result.get("ppt_filename"),
            qa_passed=result.get("qa_passed"),
            qa_issues=result.get("qa_issues", []),
        )
        if deal_id:
            from uuid import UUID

            try:
                with session_scope() as db:
                    upsert_artifact_from_pipeline(
                        db,
                        deal_id=UUID(deal_id),
                        owner_phone=phone,
                        artifact_type=result.get("artifact_type") or document_type,
                        pipeline_result=result,
                    )
            except Exception as exc:
                print(f"[artifact] Falha ao persistir artefato do deal {deal_id}: {exc}")
        log_action(
            phone,
            "job_completed",
            resource_type="job",
            resource_id=job_id,
            metadata={"qa_passed": result.get("qa_passed")},
        )
        conversation_id = (job or {}).get("conversation_id") or ""
        if conversation_id:
            from uuid import UUID

            try:
                with session_scope() as db:
                    finalize_conversation_job(
                        db,
                        conversation_id=UUID(conversation_id),
                        owner_phone=phone,
                        company_name=company_name,
                        job_id=job_id,
                        success=True,
                        deal_id=deal_id or (job or {}).get("deal_id") or "",
                    )
            except Exception as exc:
                print(f"[conversation] Falha ao finalizar job {job_id}: {exc}")
    except Exception as exc:
        error_msg = str(exc)
        if any(token in error_msg.lower() for token in ("429", "quota", "rate limit")):
            error_msg = (
                "Limite de uso da API Gemini atingido. "
                "Aguarde cerca de 1 minuto e tente novamente."
            )
        update_job(job_id, status=JobStatus.ERROR.value, error=error_msg)
        conversation_id = (job or {}).get("conversation_id") or ""
        if conversation_id:
            from uuid import UUID

            try:
                with session_scope() as db:
                    finalize_conversation_job(
                        db,
                        conversation_id=UUID(conversation_id),
                        owner_phone=phone,
                        company_name=company_name,
                        job_id=job_id,
                        success=False,
                        error=error_msg,
                        deal_id=(job or {}).get("deal_id") or "",
                    )
            except Exception as exc:
                print(f"[conversation] Falha ao registrar erro {job_id}: {exc}")
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


def run_web_job_and_notify(
    job_id: str,
    company_name: str,
    doc_type: str,
    phone: str,
    conversation_id: str = "",
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
    db: Session = Depends(get_db),
):
    from uuid import UUID

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

    deal_id = ""
    conversation_id = request.conversation_id or ""
    if conversation_id:
        try:
            conv_uuid = UUID(conversation_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="conversation_id inválido") from exc
        try:
            get_conversation_for_owner(db, conv_uuid, auth_phone)
        except ConversationNotFoundError:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        except ConversationAccessDeniedError:
            raise HTTPException(status_code=403, detail="Acesso negado")

    job_id = create_job(
        company_name,
        document_type,
        phone=auth_phone,
        client_id=auth_phone,
        deal_id=deal_id,
        conversation_id=conversation_id,
        db=db,
    )

    if conversation_id:
        try:
            deal_id = prepare_conversation_job(
                db,
                conversation_id=UUID(conversation_id),
                owner_phone=auth_phone,
                company_name=company_name,
                user_message=message,
                job_id=job_id,
            )
            update_job(job_id, deal_id=deal_id, db=db)
        except (ConversationNotFoundError, ConversationAccessDeniedError) as exc:
            _conversation_http_errors(exc)

    log_job_created(auth_phone, document_type, job_id)

    background_tasks.add_task(
        run_web_job_and_notify,
        job_id=job_id,
        company_name=company_name,
        doc_type=document_type,
        phone=auth_phone,
        conversation_id=conversation_id,
    )

    job = get_job(job_id, phone=auth_phone, db=db)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job")
    if deal_id:
        job["deal_id"] = deal_id
    if conversation_id:
        job["conversation_id"] = conversation_id
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
    if not ppt_path:
        raise HTTPException(status_code=404, detail="PPT file not found")

    filename = job.get("ppt_filename") or f"{job['company_name']}_{job['document_type']}.pptx"
    media_type = _artifact_download_media_type(job.get("document_type", "CIM"), filename)
    storage = get_artifact_storage()
    if not storage.exists(ppt_path):
        raise HTTPException(status_code=404, detail="PPT file not found")

    return storage.build_download_response(
        ppt_path,
        filename=filename,
        media_type=media_type,
    )


@app.on_event("startup")
def _startup_doc_cache_cleanup():
    cleanup_expired()
    init_db()


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
