import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    r.raise_for_status()
    return r.json()


def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=30)
    r.raise_for_status()
    return r.json()


def test_phase59_cost_perf_optimizer():
    # Create project/item/run and execute a short graph to get history
    proj = _post(
        "/projects",
        {"tenant_id": "t", "name": f"P59-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post(
        "/roadmap-items",
        {"tenant_id": "t", "project_id": proj["id"], "title": "P59 Item"},
    )
    run = _post(
        "/runs",
        {"tenant_id": "t", "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )
    # Trigger a small deterministic run (no failures)
    _post(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 1})

    # Run optimizer
    rep = _post("/self/optimize", {"run_id": run["id"], "seed": 123})
    assert rep["run_id"] == run["id"]
    assert isinstance(rep["baseline"]["cost_cents"], int)
    assert rep["outputs_equal"] is True
    # Ensure recommendations include expected keys and negative deltas
    ids = [r["id"] for r in rep["recommendations"]]
    assert set(ids) == {"caching", "async", "model_routing"}
    for r in rep["recommendations"]:
        assert r["predicted_cost_delta_cents"] <= 0


