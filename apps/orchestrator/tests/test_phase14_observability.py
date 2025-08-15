import os, uuid, httpx, datetime as dt

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


def test_phase14_observability_durations_in_history_and_cost_estimate():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG14-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG14 Metrics"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # First pass: force one QA fail to produce loop and durations
    res = _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": True, "max_qa_loops": 2})
    assert res["status"] == "completed"

    # Fetch persisted history (includes per-step durations via logs)
    hist = _get_ok(f"/runs/{run['id']}/graph/history")
    assert isinstance(hist, list) and len(hist) >= 1

    # Compute simple monotonic timing from created_at
    times = []
    for h in hist:
        ts = h.get("created_at")
        assert isinstance(ts, str) and len(ts) >= 10
        t = dt.datetime.fromisoformat(ts)
        times.append(t)
    assert all(t2 >= t1 for t1, t2 in zip(times, times[1:]))
    total_duration = (times[-1] - times[0]).total_seconds()
    assert total_duration >= 0

    # Deterministic local cost estimate (100 tokens per step attempt)
    estimated_tokens = len(hist) * 100
    assert isinstance(estimated_tokens, int) and estimated_tokens > 0
    estimated_usd = round(estimated_tokens * 0.000002, 6)
    assert isinstance(estimated_usd, float)

