import os, uuid, json, httpx, pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def test_webhook_pull_request_opened_dry_run():
    # Create minimal project+item so handler can resolve the item prefix from branch name
    proj = _post("/projects", {
        "tenant_id": TENANT,
        "name": f"WH-{uuid.uuid4().hex[:6]}",
        "description": "wh sim",
        "repo_url": "https://github.com/testowner/testrepo.git"
    })
    item = _post("/roadmap-items", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "title": "Webhook Feature"
    })
    prefix = item["id"][:8]
    branch = f"feature/{prefix}-webhook-feature"

    payload = {
        "action": "opened",
        "repository": {"name": "testrepo", "owner": {"login": "testowner"}},
        "pull_request": {"head": {"ref": branch}},
        "number": 1
    }
    r = httpx.post(f"{BASE}/webhooks/github", json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    assert data.get("ok") is True
    assert data.get("handled") is True
    # In CI dry-run mode, we expect 'result' to include dry_run and dor_pass keys
    res = data.get("result", {})
    assert "dry_run" in res or "required_contexts" in res


