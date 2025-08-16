import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=60)
    r.raise_for_status()
    return r.json()


def test_budget_threshold_block_and_resume():
    # Dry-run GitHub writes
    os.environ["GITHUB_WRITE_ENABLED"] = "0"

    proj = _post("/projects", {"tenant_id": TENANT, "name": f"BGS-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "Budget Status"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    _post(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})

    # Force block by setting block_pct very low
    res_block = _post(f"/integrations/budget/{run['id']}/compute", {
        "warn_pct": 0.1,
        "block_pct": 0.1,
        "rate": {"usd_per_1k_tokens": 0.01}
    })
    assert res_block["status"] == "blocked"

    # Re-compute with higher threshold -> should be ok/warn
    res_ok = _post(f"/integrations/budget/{run['id']}/compute", {
        "warn_pct": 0.9,
        "block_pct": 1.0,
        "rate": {"usd_per_1k_tokens": 0.01}
    })
    assert res_ok["status"] in {"ok", "warn"}


