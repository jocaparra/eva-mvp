from pathlib import Path

from app.state import JobState


def qa_node(state: JobState) -> dict:
    ppt_path = state.get("ppt_path", "")
    issues: list[str] = []

    if state.get("error"):
        issues.append(state["error"])

    if not ppt_path or not Path(ppt_path).exists():
        issues.append("PPT file was not generated or does not exist.")
        return {"qa_passed": False, "qa_issues": issues}

    file_size = Path(ppt_path).stat().st_size
    if file_size < 1024:
        issues.append(f"PPT file is too small ({file_size} bytes).")

    return {"qa_passed": len(issues) == 0, "qa_issues": issues}
