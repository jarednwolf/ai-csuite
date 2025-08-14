import os, uuid
import httpx
import pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

@pytest.mark.e2e
def test_run_start_auto_ensure_no_pr():
    # Arrange: project WITHOUT repo_url so PR step is skipped (safe local test)
    proj = _post("/projects", {
        "tenant_id": TENANT,
        "name": f"AutoEnsure-{uuid.uuid4().hex[:6]}",
        "description": "e2e no-pr",
        "repo_url": ""  # empty => open_pr_for_run() will skip
    })
    item = _post("/roadmap-items", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "title": "AutoEnsure E2E"
    })
    run = _post("/runs", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "roadmap_item_id": item["id"],
        "phase": "delivery"
    })

    # Act: start run (should auto-ensure artifacts, pass DoR, and not block)
    started = _post(f"/runs/{run['id']}/start", {})

    # Assert
    assert started["status"] == "succeeded"
    # PR step skipped (repo_url empty)
    assert "pr_url" not in started
    assert started.get("pr_skipped") is not None


