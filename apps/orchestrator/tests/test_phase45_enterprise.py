from fastapi.testclient import TestClient
from orchestrator.app import app


def test_phase45_sso_and_audit_export():
    client = TestClient(app)

    # Configure OIDC SSO
    cfg = {
        "tenant_id": "t-enterprise",
        "protocol": "oidc",
        "config": {"issuer": "https://idp.example/", "client_id": "abc", "client_secret": "xyz"}
    }
    res = client.post("/auth/sso/config", headers={"X-Role": "admin"}, json=cfg)
    assert res.status_code == 200, res.text
    cid = res.json()["config_id"]
    assert cid

    # Audit export JSON
    exp_json = client.get("/audit/export", headers={"X-Role": "viewer"}, params={"tenant_id": "t-enterprise", "fmt": "json"})
    assert exp_json.status_code == 200, exp_json.text
    items = exp_json.json()["items"]
    assert isinstance(items, list)

    # Audit export CSV
    exp_csv = client.get("/audit/export", headers={"X-Role": "viewer"}, params={"tenant_id": "t-enterprise", "fmt": "csv"})
    assert exp_csv.status_code == 200, exp_csv.text
    assert exp_csv.json()["text"].endswith("\n")


