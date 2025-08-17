from fastapi.testclient import TestClient
from orchestrator.app import app


def test_phase44_billing_usage_and_invoice():
    client = TestClient(app)
    tenant = "tenant-44"

    # Set plan
    r = client.post("/billing/plan/set", headers={"X-Role": "admin"}, json={"tenant_id": tenant, "plan": "hosted"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "hosted"

    # Get usage
    usage = client.get("/billing/usage", headers={"X-Role": "viewer"}, params={"tenant_id": tenant})
    assert usage.status_code == 200, usage.text
    u = usage.json()
    assert u["tenant_id"] == tenant
    assert set(u["meters"].keys()) == {"tokens", "runs", "preview_minutes", "storage_mb", "api_calls"}

    # Invoice
    inv = client.post("/billing/invoice/mock", headers={"X-Role": "viewer"}, json={"tenant_id": tenant})
    assert inv.status_code == 200, inv.text
    j = inv.json()
    assert j["tenant_id"] == tenant
    assert isinstance(j["amount_cents"], int)


