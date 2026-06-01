from langgraph.graph import END, StateGraph

from app.agents.document import document_node
from app.agents.financial import financial_node
from app.agents.qa import qa_node
from app.agents.research import research_node
from app.state import JobState


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


def run_pipeline(job_id: str, company_name: str, document_type: str) -> JobState:
    graph = build_graph()
    initial_state: JobState = {
        "job_id": job_id,
        "company_name": company_name,
        "document_type": document_type,
    }
    return graph.invoke(initial_state)
