from fastapi.testclient import TestClient
from orchestrator.app import app


def test_phase46_cockpit_endpoints():
    client = TestClient(app)

    # Seed some data via existing endpoints
    client.post("/attribution/report/run", json={"from_date": "2025-01-01", "to_date": "2025-01-31"})
    client.post("/experiments/start", json={"experiment_id": "exp-46", "plan": {"variants": {"A": 0.5, "B": 0.5}}, "seed": 124})
    client.post("/planning/roi/score", headers={"X-Role": "admin"}, json={"tenant_id": "t-46", "project_id": "p-46", "idea_id": "i-1", "cost_cents": 100})

    # Lists
    ex = client.get("/cockpit/experiments", headers={"X-Role": "viewer"})
    assert ex.status_code == 200, ex.text
    ca = client.get("/cockpit/campaigns", headers={"X-Role": "viewer"})
    assert ca.status_code == 200, ca.text
    au = client.get("/cockpit/audiences", headers={"X-Role": "viewer"})
    assert au.status_code == 200, au.text
    roi = client.get("/cockpit/roi", headers={"X-Role": "viewer"}, params={"tenant_id": "t-46", "project_id": "p-46"})
    assert roi.status_code == 200, roi.text

    # Control actions
    ks = client.post("/cockpit/actions/kill-switch", headers={"X-Role": "admin"}, params={"resource": "ads", "enable": True})
    assert ks.status_code == 200, ks.text
    ra = client.post("/cockpit/actions/ramp", headers={"X-Role": "admin"}, params={"feature": "llm-candidate", "percent": 25})
    assert ra.status_code == 200, ra.text
    ap = client.post("/cockpit/actions/approve-spend", headers={"X-Role": "admin"}, params={"campaign_id": "camp-1", "amount_cents": 1234})
    assert ap.status_code == 200, ap.text


