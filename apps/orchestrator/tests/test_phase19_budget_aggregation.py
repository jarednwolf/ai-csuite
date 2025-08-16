import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=60)
    r.raise_for_status()
    return r.json()

def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_budget_compute_and_get_idempotent():
    # Ensure dry-run for GitHub to avoid network
    os.environ["GITHUB_WRITE_ENABLED"] = "0"

    proj = _post("/projects", {"tenant_id": TENANT, "name": f"BUD-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "Budget Feature"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    # Execute a full graph run to generate deterministic history
    _post(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})

    # Compute budget with defaults (warn 0.8, block 1.0)
    res1 = _post(f"/integrations/budget/{run['id']}/compute", {"rate": {"usd_per_1k_tokens": 0.01}})
    assert res1["status"] in {"ok", "warn", "blocked"}
    assert "totals" in res1 and "personas" in res1
    assert isinstance(res1["totals"]["cost_cents"], int)

    # Re-run compute; should update in-place (idempotent), same totals
    res2 = _post(f"/integrations/budget/{run['id']}/compute", {"rate": {"usd_per_1k_tokens": 0.01}})
    assert res2["totals"]["cost_cents"] == res1["totals"]["cost_cents"]

    # GET returns the latest record
    got = _get(f"/integrations/budget/{run['id']}")
    assert got["totals"]["cost_cents"] == res1["totals"]["cost_cents"]
    assert got["status"] == res2["status"]


