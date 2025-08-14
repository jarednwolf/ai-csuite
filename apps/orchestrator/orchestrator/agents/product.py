def draft_prd(project_name: str, item_title: str, references: list[str] | None = None) -> dict:
    """Return a stubbed PRD JSON with AC and metrics, plus optional references from RAG."""
    prd = {
        "title": f"{project_name}: {item_title}",
        "problem": "Users struggle to complete this task quickly.",
        "user_stories": [
            {"as_a": "user", "i_want": "to complete the task faster", "so_that": "I save time"}
        ],
        "acceptance_criteria": [
            {"id": "AC-1", "given": "a logged-in user", "when": "they perform the task", "then": "it completes within 3 steps"}
        ],
        "metrics": [{"name": "task_time_reduction", "target": ">=15%"}],
        "risks": [{"risk": "scope creep", "mitigation": "tight AC and feature flag"}]
    }
    if references:
        prd["references"] = references
    return prd


