import os, uuid, httpx, pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def _get(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()

@pytest.mark.requires_github
def test_phase7_statuses_and_merge():
    if not os.getenv("GITHUB_TOKEN"):
        pytest.skip("GITHUB_TOKEN not set; skipping live GitHub test")

    owner = os.getenv("E2E_REPO_OWNER")
    repo = os.getenv("E2E_REPO_NAME")
    if not (owner and repo):
        pytest.skip("E2E_REPO_OWNER/E2E_REPO_NAME not set")

    proj = _post("/projects", {
        "tenant_id": TENANT,
        "name": f"GH-E2E-{uuid.uuid4().hex[:6]}",
        "description": "live gh",
        "repo_url": f"https://github.com/{owner}/{repo}.git"
    })

    item = _post("/roadmap-items", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "title": "Live GH Flow"
    })

    run = _post("/runs", {
        "tenant_id": TENANT,
        "project_id": proj["id"],
        "roadmap_item_id": item["id"],
        "phase": "delivery"
    })

    start_res = _post(f"/runs/{run['id']}/start", {})
    assert start_res["status"] == "succeeded"
    assert "pr_url" in start_res

    # Statuses
    st = _get(f"/integrations/github/pr/{run['id']}/statuses")
    contexts = {s["context"]: s["state"] for s in st["statuses"]}
    assert contexts.get("ai-csuite/dor") == "success"
    assert st["can_merge"] is False  # human approval pending

    # Approve -> can merge
    st2 = _post(f"/integrations/github/pr/{run['id']}/approve", {})
    assert st2["can_merge"] is True

    # Merge
    merged = _post(f"/integrations/github/pr/{run['id']}/merge", {})
    assert merged["merged"] is True


