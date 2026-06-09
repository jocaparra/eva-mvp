from pathlib import Path

from app.agents.qa_factual import run_factual_qa
from app.state import JobState


def qa_node(state: JobState) -> dict:
    file_path = state.get("file_path") or state.get("ppt_path", "")
    issues: list[str] = list(state.get("qa_issues") or [])

    if state.get("error"):
        issues.append(state["error"])

    if not file_path or not Path(file_path).exists():
        issues.append("Artefato não foi gerado ou não existe.")
        return {"qa_passed": False, "qa_issues": issues}

    file_size = Path(file_path).stat().st_size
    if file_size < 1024:
        issues.append(f"Arquivo gerado é pequeno demais ({file_size} bytes).")

    merged_state = dict(state)
    merged_state["qa_issues"] = issues
    merged_state["file_path"] = file_path
    factual = run_factual_qa(merged_state)

    return {
        "qa_passed": factual["qa_passed"] and file_size >= 1024,
        "qa_issues": factual["qa_issues"],
        "audit_mode": factual["audit_mode"],
        "field_audits": factual.get("field_audits", {}),
    }
