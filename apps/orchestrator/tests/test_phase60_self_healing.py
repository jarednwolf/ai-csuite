import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    r.raise_for_status()
    return r.json()


def test_phase60_self_healing_revert_and_bisect():
    # Setup run
    proj = _post(
        "/projects",
        {"tenant_id": "t", "name": f"P60-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post(
        "/roadmap-items",
        {"tenant_id": "t", "project_id": proj["id"], "title": "P60 Item"},
    )
    run = _post(
        "/runs",
        {"tenant_id": "t", "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # Revert incident
    rev = _post("/incidents/revert", {"run_id": run["id"], "reason": "slo_breach"})
    assert rev["status"] == "created"
    assert rev["incident_id"] and rev["path"].endswith(".json")

    # Bisect incident
    bi = _post("/incidents/bisect", {"run_id": run["id"], "start_sha": "a1b2c3d", "end_sha": "e4f5g6h"})
    assert bi["status"] == "created"
    assert bi["incident_id"] and bi["path"].endswith(".json")


