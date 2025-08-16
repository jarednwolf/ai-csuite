import os
import uuid

import pytest
from fastapi.testclient import TestClient
from orchestrator.app import app
client = TestClient(app)


def _reset_env_for_dry_run():
    os.environ["GITHUB_WRITE_ENABLED"] = "0"
    os.environ["GITHUB_PR_ENABLED"] = "0"
    os.environ["PREVIEW_ENABLED"] = "1"
    os.environ["PREVIEW_BASE_URL"] = "http://preview.local"


def test_preview_deploy_and_smoke_dry_run():
    _reset_env_for_dry_run()
    run_id = str(uuid.uuid4())

    # Deploy (dry-run): should return pending and deterministic preview URL
    body = {"owner": "acme", "repo": "demo", "branch": "feature/test-preview"}
    r = client.post(f"/integrations/preview/{run_id}/deploy", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "pending"
    assert data["preview_url"].startswith("http://preview.local/")

    # Smoke: success, statuses simulated, summary materialized in response
    r2 = client.post(f"/integrations/preview/{run_id}/smoke", json={})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["ok"] is True
    assert d2["status"] == "success"
    assert d2["preview_url"] == data["preview_url"]
    assert "summary" in d2  # simulated summary body included
    statuses = d2.get("statuses", [])
    # confirm ai-csuite/preview-smoke is success in simulated statuses
    assert any(s.get("context") == "ai-csuite/preview-smoke" and s.get("state") == "success" for s in statuses)

    # Idempotency: re-run deploy and smoke
    r3 = client.post(f"/integrations/preview/{run_id}/deploy", json=body)
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["status"] == "pending"
    # smoke again should remain success and not duplicate ledger
    r4 = client.post(f"/integrations/preview/{run_id}/smoke", json={})
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["status"] == "success"

    # GET info returns current record
    g = client.get(f"/integrations/preview/{run_id}")
    assert g.status_code == 200
    gi = g.json()
    assert gi["preview_url"] == data["preview_url"]
    assert gi["status"] in ("pending", "success")


def test_preview_unknown_run_id_404():
    _reset_env_for_dry_run()
    run_id = "not-found"
    r = client.post(f"/integrations/preview/{run_id}/smoke", json={})
    assert r.status_code == 404
    assert "not found" in r.text.lower()


def test_preview_smoke_injected_failure_then_success():
    _reset_env_for_dry_run()
    run_id = str(uuid.uuid4())
    body = {"owner": "acme", "repo": "demo", "branch": "feature/fail-preview"}

    # Deploy
    r = client.post(f"/integrations/preview/{run_id}/deploy", json=body)
    assert r.status_code == 200

    # First smoke with failure injection
    r2 = client.post(f"/integrations/preview/{run_id}/smoke", json={"inject_fail": True})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "failure"

    # Resume: smoke again without injection succeeds
    r3 = client.post(f"/integrations/preview/{run_id}/smoke", json={})
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["status"] == "success"


