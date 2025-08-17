from fastapi.testclient import TestClient
from orchestrator.app import app


def test_test_synthesis_suggestions():
    client = TestClient(app)
    res = client.post("/self/tests/suggest", json={"target": "apps/orchestrator/orchestrator/api"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("version") == 1
    assert isinstance(data.get("suggestions"), list)
    assert any(s["path"].endswith(".py") for s in data.get("suggestions"))


