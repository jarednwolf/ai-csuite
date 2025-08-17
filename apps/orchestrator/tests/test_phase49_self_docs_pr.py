from fastapi.testclient import TestClient
from orchestrator.app import app


def test_self_docs_pr_plan():
    client = TestClient(app)
    payload = {
        "title": "Docs: Update checklist",
        "summary": "Append phases 47–53",
        "changes": {"docs/PHASE_TRACKING_CHECKLIST.md": "+ phases"},
    }
    res = client.post("/self/pr/docs", json=payload)
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan.get("status") == "planned"
    assert plan.get("status_context") == "ai-csuite/self-docs"
    assert "docs/PHASE_TRACKING_CHECKLIST.md" in plan.get("files", [])


