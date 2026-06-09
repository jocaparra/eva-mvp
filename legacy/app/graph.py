from langgraph.graph import END, StateGraph

from app.agents.document import document_node
from app.agents.financial import financial_node
from app.agents.qa import qa_node
from app.agents.research import research_node
from app.state import JobState


from app.artifact_types import resolve_artifact_type


def build_graph():
    graph = StateGraph(JobState)

    graph.add_node("research", research_node)
    graph.add_node("financial", financial_node)
    graph.add_node("document", document_node)
    graph.add_node("qa", qa_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "financial")
    graph.add_edge("financial", "document")
    graph.add_edge("document", "qa")
    graph.add_edge("qa", END)

    return graph.compile()


def run_pipeline(
    job_id: str,
    company_name: str,
    document_type: str,
    client_id: str = "default",
    client_context: str = "",
    deal_id: str = "",
) -> JobState:
    graph = build_graph()
    artifact_type = resolve_artifact_type(document_type)
    initial_state: JobState = {
        "job_id": job_id,
        "company_name": company_name,
        "document_type": document_type,
        "client_id": client_id,
        "client_context": client_context or "",
        "deal_id": deal_id or "",
        "retrieved_context": [],
        "research_citations": [],
        "financial_citations": [],
        "audit_mode": "full" if deal_id else "legacy",
        "artifact_type": artifact_type,
    }
    return graph.invoke(initial_state)
