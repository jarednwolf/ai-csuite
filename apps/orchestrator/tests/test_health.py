
from fastapi.testclient import TestClient
from orchestrator.app import app

def test_health():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

def test_run_lifecycle():
    client = TestClient(app)
    payload = {
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "project_id": "11111111-1111-1111-1111-111111111111",
        "roadmap_item_id": None,
        "phase": "delivery"
    }
    r = client.post("/runs", json=payload)
    assert r.status_code == 200
    run = r.json()
    assert "id" in run
    r2 = client.get(f"/runs/{run['id']}")
    assert r2.status_code == 200

