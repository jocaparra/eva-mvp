from typing import TypedDict


class Citation(TypedDict, total=False):
    """Referência rastreável a um trecho do data room ou fonte externa."""

    source_file: str
    page: int
    chunk_id: str
    quote: str
    source: str  # data_room | external


class DealState(TypedDict, total=False):
    """Estado persistido de um deal workspace (domínio)."""

    deal_id: str
    company_name: str
    documents: list
    retrieved_context: list[Citation]
    artifacts: list
    status: str


class JobState(TypedDict, total=False):
    """Estado efêmero do pipeline LangGraph (compatibilidade com fluxo atual)."""

    job_id: str
    deal_id: str
    company_name: str
    document_type: str
    research_data: str
    research_structured: dict
    logo_path: str
    kpis: dict
    financial_structured: dict
    revenue_history: list
    revenue_breakdown: list
    ppt_path: str
    ppt_filename: str
    edit_url: str
    client_id: str
    client_context: str
    retrieved_context: list[Citation]
    research_citations: list[Citation]
    financial_citations: list[Citation]
    audit_mode: str
    field_audits: dict
    artifact_type: str
    file_path: str
    file_filename: str
    qa_passed: bool
    qa_issues: list[str]
    error: str
