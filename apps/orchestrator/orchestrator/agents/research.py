def synthesize(project_name: str, item_title: str, related_snippets: list[str] | None = None) -> dict:
    """Return a stubbed research summary with evidence links; append RAG snippets if provided."""
    evidence = [
        "https://example.com/interview-notes-1",
        "https://example.com/survey-snapshot"
    ]
    if related_snippets:
        # Tag RAG evidence so it's distinguishable
        evidence.extend([f"RAG: {s}" for s in related_snippets])
    return {
        "summary": f"Users strongly prefer the '{item_title}' improvement; early interviews suggest it reduces task time by ~15-20%.",
        "evidence": evidence
    }


