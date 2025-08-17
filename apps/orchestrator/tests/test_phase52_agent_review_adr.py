from fastapi.testclient import TestClient
from orchestrator.app import app


def test_agent_review_adr_skeleton():
    client = TestClient(app)
    res = client.post("/self/review", json={"diff_summary": "docs-only changes", "links": ["/diff/1"]})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out.get("version") == 1
    assert "steelman" in out and "options" in out and "decision" in out and "owner" in out


