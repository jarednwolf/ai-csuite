import os, uuid, httpx, pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=90)
    r.raise_for_status()
    return r.json()

def _get(path):
    r = httpx.get(f"{BASE}{path}", timeout=90)
    r.raise_for_status()
    return r.json()

@pytest.mark.requires_github
def test_pr_summary_comment_roundtrip():
    if not os.getenv("GITHUB_TOKEN"):
        pytest.skip("GITHUB_TOKEN not set")
    owner = os.getenv("E2E_REPO_OWNER")
    repo = os.getenv("E2E_REPO_NAME")
    if not (owner and repo):
        pytest.skip("E2E_REPO_OWNER/E2E_REPO_NAME not set")

    proj = _post("/projects", {
        "tenant_id": TENANT,
        "name": f"PRC-{uuid.uuid4().hex[:6]}",
        "description": "comment",
        "repo_url": f"https://github.com/{owner}/{repo}.git"
    })
    item = _post("/roadmap-items", {
        "tenant_id": TENANT, "project_id": proj["id"], "title": "PR Comment Feature"
    })
    run = _post("/runs", {
        "tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"
    })
    start = _post(f"/runs/{run['id']}/start", {})
    assert start.get("pr_url")

    # Refresh comment explicitly
    res = _post(f"/integrations/github/pr/{run['id']}/comment/refresh", {})
    assert res.get("comment_id")

    # Verify the comment exists on GitHub (marker present)
    token = os.getenv("GITHUB_TOKEN")
    branch = start["branch"]
    number = start["pr_number"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    rr = httpx.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments", headers=headers, timeout=60)
    rr.raise_for_status()
    comments = rr.json()
    assert any(("ai-csuite:summary" in c.get("body","") and branch in c.get("body","")) for c in comments)


