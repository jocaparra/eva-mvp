from typing import TypedDict


class JobState(TypedDict, total=False):
    job_id: str
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
    qa_passed: bool
    qa_issues: list[str]
    error: str
