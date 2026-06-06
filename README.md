# EVA — Confidential Information Memorandum Agent

EVA is an autonomous M&A agent that generates CIMs, valuations and due diligence documents with deal workspace, RAG, traceable citations, factual QA and human approval.

## Stack

- **FastAPI** — HTTP API and background job orchestration
- **LangGraph** — sequential agent pipeline (research → financial → document → qa)
- **LangChain + Anthropic Claude** — LLM synthesis and KPI extraction
- **Voyage AI** — embeddings for RAG (Anthropic-recommended partner)
- **SQLAlchemy + Postgres** — **fonte de verdade** (deals, documentos, artefatos, jobs, conversas, RAG)
- **Tavily / Yahoo Finance** — research and financial data (marked `external` when used)
- **python-pptx / python-docx** — document generation

## Prerequisites

- Python 3.11+
- **DATABASE_URL** — Postgres in production (SQLite `eva_workspace.db` in local dev if omitted)
- **JWT_SECRET_KEY** — auth for the web platform
- **ANTHROPIC_API_KEY**, **TAVILY_API_KEY** — pipeline LLM and search
- **VOYAGE_API_KEY** — embeddings for data room RAG (optional in dev/tests)

### Optional

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` + `SUPABASE_KEY` | Painel **Arquivos** (`/files`), assinaturas WhatsApp, `ARTIFACT_STORAGE=supabase` |
| `ARTIFACT_STORAGE` | `local` (default), `supabase`, or `s3` for generated artifacts |
| `PRESENTON_API_KEY` | PPT generation via Presenton |

**The web product runs without Supabase.** Deals, conversations, jobs, ingestion and downloads use SQLAlchemy only. No product route returns 503 when Supabase is missing.

## Setup

```bash
cd eva-mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill DATABASE_URL, JWT_SECRET_KEY, ANTHROPIC_API_KEY, TAVILY_API_KEY

alembic upgrade head   # production Postgres
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Deploy Railway:** ver [DEPLOY.md](DEPLOY.md).

## Web platform flow (unified)

1. Login → create **conversation**
2. Attach PDF → `POST /conversations/{id}/documents` (ingestion + RAG)
3. Send "CIM da [empresa]" → `POST /jobs/web` (job in SQLAlchemy)
4. Artifact persisted on deal → review citations/QA in UI → **Approve**
5. Download → `GET /deals/{deal_id}/artifacts/{artifact_id}/download`

### Key endpoints

```bash
# Deals (SQLAlchemy)
GET  /deals
GET  /deal/{deal_id}
GET  /deals/{deal_id}/artifacts/{artifact_id}      # review: field_audits, QA
POST /deals/{deal_id}/artifacts/{artifact_id}/approve

# Conversations
POST /conversations
POST /conversations/{id}/documents                  # data room upload
POST /conversations/{id}/messages
POST /jobs/web                                      # generation from chat

# Jobs
GET  /jobs/{job_id}/status
```

## Deal workspace (API)

```bash
curl -X POST http://localhost:8000/deals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Empresa Alvo Ltda"}'

curl -X POST "http://localhost:8000/deals/{deal_id}/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data-room.pdf"
```

## Tests

```bash
pytest tests/ -v
```

Stage-specific: `test_deal_workspace_stage1.py`, `test_ingestion_stage2.py`, `test_research_stage3.py`, `test_qa_stage4.py`, `test_approval_stage5.py`, `test_generation_stage6.py`, `test_deals_unified_stage1.py`, `test_jobs_web_stage3.py`, `test_artifact_storage_stage4.py`, `test_cleanup_stage6.py`, `test_e2e_smoke_stage7.py`.

### Smoke E2E (etapa 7)

Offline (CI, pipeline mockado):

```bash
pytest tests/test_e2e_smoke_stage7.py -v
```

Manual com Postgres + chaves reais: login na plataforma → anexar PDF no chat → "CIM da [empresa]" → aguardar job → revisar citações → baixar → aprovar. Sem `SUPABASE_URL`.

## Pipeline

```
research → financial → document → qa → persist artifact + storage
```

| Step | Agent | Description |
|------|-------|-------------|
| research | Tavily + RAG | Company data; data room first |
| financial | RAG + yfinance | KPIs with citations |
| document | pptx/docx | Parametric generation |
| qa | factual audit | CITED / DIVERGENT / UNCITED per field |

## Project structure

```
eva-mvp/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── database.py          # SQLAlchemy (import app.models before create_all)
│   ├── jobs_store.py        # generation_jobs (SQLAlchemy)
│   ├── storage/             # ARTIFACT_STORAGE local|supabase|s3
│   ├── repositories/        # deal_workspace, conversations, artifacts
│   ├── generation/          # generate(artifact_type, deal_state)
│   └── agents/
├── alembic/versions/
├── frontend/platform.html
├── artifact_storage/        # local artifact files (gitignored)
├── uploads/deal_workspace/  # ingested PDFs for RAG
└── outputs/                 # ephemeral pipeline output (copied to storage)
```
