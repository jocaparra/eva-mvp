# EVA — Confidential Information Memorandum Agent

EVA is an autonomous agent that receives a company name and generates a CIM (Confidential Information Memorandum) in PowerPoint format.

## Stack

- **FastAPI** — HTTP API and background job orchestration
- **LangGraph** — sequential agent pipeline (research → financial → document → qa)
- **LangChain + Google Gemini** — LLM synthesis and KPI extraction
- **Tavily** — web search for company research
- **Yahoo Finance (yfinance)** — financial KPIs
- **SQLAlchemy + Postgres** — deal workspace persistente (documentos, artefatos, citações)
- **python-pptx** — PowerPoint generation

## Prerequisites

- Python 3.11+
- Google API key ([aistudio.google.com](https://aistudio.google.com))
- Tavily API key ([tavily.com](https://tavily.com))

## Setup

```bash
# Clone and enter the project
cd eva-mvp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys

# Banco (deal workspace) — opcional em dev (usa SQLite local eva_workspace.db)
# alembic upgrade head
```

## Deal workspace (novo fluxo)

Persistência SQLAlchemy para deals com data room, artefatos e citações.

```bash
# Criar deal (requer JWT)
curl -X POST http://localhost:8000/deals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Empresa Alvo Ltda"}'

# Ler deal
curl http://localhost:8000/deals/{deal_id} \
  -H "Authorization: Bearer $TOKEN"
```

Migrations:

```bash
alembic upgrade head
```

Testes da etapa 1:

```bash
pytest tests/test_deal_workspace_stage1.py -v
```

### Upload e ingestão (data room)

```bash
# Upload PDF para o deal
curl -X POST "http://localhost:8000/deals/{deal_id}/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/caminho/para/data-room.pdf"
```

Testes da etapa 2:

```bash
pytest tests/test_ingestion_stage2.py -v
```

Testes da etapa 3 (RAG + citações):

```bash
pytest tests/test_research_stage3.py -v
```

Testes da etapa 4 (QA factual):

```bash
pytest tests/test_qa_stage4.py -v
```

### Aprovação humana (etapa 5)

```bash
# Gerar artefato vinculado ao deal
curl -X POST "http://localhost:8000/deals/{deal_id}/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Gerar CIM da Empresa Alvo"}'

# Revisar audit por campo (status, delta, citação, chunks buscados)
curl "http://localhost:8000/deals/{deal_id}/artifacts/{artifact_id}" \
  -H "Authorization: Bearer $TOKEN"

# Aprovar (override exige override_reason quando há issues bloqueantes)
curl -X POST "http://localhost:8000/deals/{deal_id}/artifacts/{artifact_id}/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"override_reason": "Validado com CFO em call."}'
```

Testes da etapa 5:

```bash
pytest tests/test_approval_stage5.py -v
```

### Gerador parametrizado (etapa 6)

```python
from app.generation import generate

result = generate("cim_pptx", deal_state)   # ou "memo_docx"
# result.file_path, result.artifact_type, result.mime_type
```

Tipos suportados: `cim_pptx`, `memo_docx`. `model_xlsx` fica fora (proveniência por célula).

Testes da etapa 6:

```bash
pytest tests/test_generation_stage6.py -v
```

Suite completa:

```bash
pytest tests/ -v
```

## Running locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Usage

### 1. Create a job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Apple Inc"}'
```

Response (202 Accepted):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "company_name": "Apple Inc",
  "status": "pending",
  "ppt_path": null,
  "qa_passed": null,
  "qa_issues": null,
  "error": null
}
```

### 2. Check job status

```bash
curl http://localhost:8000/jobs/{job_id}/status
```

Status values: `pending` → `running` → `done` | `error`

### 3. Download the CIM

```bash
curl -OJ http://localhost:8000/jobs/{job_id}/download
```

The generated file is also saved at `outputs/{job_id}.pptx`.

## Pipeline

```
research → financial → document → qa
```

| Step       | Agent        | Description                                      |
|------------|--------------|--------------------------------------------------|
| research   | Tavily + LLM | Web search and synthesis of company data         |
| financial  | yfinance + LLM | KPI extraction from Yahoo Finance + research    |
| document   | python-pptx  | PPT generation with fixed CIM template           |
| qa         | python-pptx  | Validates all required sections are present      |

## Project structure

```
eva-mvp/
├── app/
│   ├── main.py          # FastAPI routes
│   ├── graph.py         # LangGraph pipeline
│   ├── state.py         # Shared JobState
│   └── agents/
│       ├── research.py
│       ├── financial.py
│       ├── document.py
│       └── qa.py
├── outputs/             # Generated PPT files
├── requirements.txt
├── .env.example
└── README.md
```
