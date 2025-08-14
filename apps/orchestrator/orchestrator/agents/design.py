def review_ui(project_name: str, item_title: str) -> dict:
    """Return a stubbed heuristics/a11y review."""
    notes = (
        f"Quick pass for {project_name} / {item_title}: "
        "clear visibility of system status; match between system & real world; "
        "basic keyboard navigability present."
    )
    return {
        "passes": True,
        "heuristics_score": 92,
        "a11y_notes": notes,
    }


