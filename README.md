# EVA — Confidential Information Memorandum Agent

EVA is an autonomous agent that receives a company name and generates a CIM (Confidential Information Memorandum) in PowerPoint format.

## Stack

- **FastAPI** — HTTP API and background job orchestration
- **LangGraph** — sequential agent pipeline (research → financial → document → qa)
- **LangChain + Google Gemini** — LLM synthesis and KPI extraction
- **Tavily** — web search for company research
- **Yahoo Finance (yfinance)** — financial KPIs
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
