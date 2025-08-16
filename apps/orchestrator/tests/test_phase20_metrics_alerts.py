import os
import uuid
import httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"


def _post_ok(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_ok(p):
    r = httpx.get(f"{BASE}{p}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_alerts_slo_burn_force_and_clear():
    os.environ["GITHUB_WRITE_ENABLED"] = "0"
    os.environ["GITHUB_PR_ENABLED"] = "0"
    os.environ["ALERTS_ENABLED"] = "1"

    proj = _post_ok("/projects", {"tenant_id": TENANT, "name": f"OPS-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post_ok("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "Ops SLO"})
    run = _post_ok("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    # Start with a single injected failure to ensure at least one error attempt in history
    _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2, "inject_failures": {"product": 1}})

    # Force SLO burn by setting burn_pct=0.0
    comp = _post_ok(f"/integrations/alerts/{run['id']}/compute", {"burn_pct": 0.0})
    assert comp["status"] == "alerts"
    assert any(a.get("type") == "slo_burn" for a in comp.get("alerts", []))
    # Idempotent re-run should not duplicate alerts and may return simulated status in dry-run
    comp2 = _post_ok(f"/integrations/alerts/{run['id']}/compute", {"burn_pct": 0.0})
    assert comp2["status"] == "alerts"

    # Raise threshold high to clear SLO burn; no other alerts should block success
    comp3 = _post_ok(f"/integrations/alerts/{run['id']}/compute", {"burn_pct": 1.0})
    assert comp3["status"] in {"ok", "alerts"}
    # If still alerts, they must not be 'slo_burn'
    if comp3["status"] == "alerts":
        assert all(a.get("type") != "slo_burn" for a in comp3.get("alerts", []))

    # Snapshot endpoint returns latest
    snap = _get_ok(f"/integrations/alerts/{run['id']}")
    assert snap["run_id"] == run["id"]


def test_alerts_retry_exhaust_and_budget_overflow():
    os.environ["GITHUB_WRITE_ENABLED"] = "0"
    os.environ["GITHUB_PR_ENABLED"] = "0"
    os.environ["ALERTS_ENABLED"] = "1"

    proj = _post_ok("/projects", {"tenant_id": TENANT, "name": f"OPS-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post_ok("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "Ops Alerts"})
    run = _post_ok("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    # Trigger retry exhaustion on 'engineer' by injecting 3 failures (max attempts)
    try:
        httpx.post(f"{BASE}/runs/{run['id']}/graph/start", json={"inject_failures": {"engineer": 3}}, timeout=60).raise_for_status()
    except httpx.HTTPStatusError:
        # Expected failure due to retry exhausted
        pass

    # Compute should detect retry_exhaust and return alerts; include dry-run simulated status context
    comp = _post_ok(f"/integrations/alerts/{run['id']}/compute", {})
    assert comp["status"] == "alerts"
    types = [a.get("type") for a in comp.get("alerts", [])]
    assert "retry_exhaust" in types
    # Simulated statuses for dry-run should include ai-csuite/alerts context
    statuses = comp.get("statuses", [])
    assert any(s.get("context") == "ai-csuite/alerts" for s in statuses)
    # Summary should contain Operations section
    if "summary" in comp:
        assert "### Operations" in comp["summary"]

    # Budget: force blocked totals then recompute alerts should include budget_overflow
    _post_ok(f"/integrations/budget/{run['id']}/compute", {"warn_pct": 0.1, "block_pct": 0.1, "rate": {"usd_per_1k_tokens": 0.01}})
    comp2 = _post_ok(f"/integrations/alerts/{run['id']}/compute", {})
    types2 = [a.get("type") for a in comp2.get("alerts", [])]
    assert "budget_overflow" in types2


