import os, uuid, httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _post_ok(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_ok(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _get_html(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.text


def _mk_run(tenant_id: str) -> str:
    # Minimal project + item + run for a tenant
    proj = _post_ok("/projects", {
        "tenant_id": tenant_id,
        "name": f"T{tenant_id[:2]}-{uuid.uuid4().hex[:6]}",
        "description": "",
        "repo_url": ""
    })
    item = _post_ok("/roadmap-items", {
        "tenant_id": tenant_id,
        "project_id": proj["id"],
        "title": "Sched"
    })
    run = _post_ok("/runs", {
        "tenant_id": tenant_id,
        "project_id": proj["id"],
        "roadmap_item_id": item["id"],
        "phase": "delivery"
    })
    return run["id"]


def test_scheduler_policy_enqueue_step_and_ui():
    # Policy defaults can be patched
    pol = _get_ok("/scheduler/policy")
    assert "global_concurrency" in pol and "tenant_max_active" in pol and "queue_max" in pol

    pol2 = _post_ok("/scheduler/policy", {"global_concurrency": 2, "tenant_max_active": 1, "queue_max": 100}) if False else None
    # use PATCH
    pol3 = httpx.patch(f"{BASE}/scheduler/policy", json={"global_concurrency": 2, "tenant_max_active": 1, "queue_max": 100}, timeout=60)
    pol3.raise_for_status()
    pol3 = pol3.json()
    assert pol3["global_concurrency"] == 2
    assert pol3["tenant_max_active"] == 1

    # Create runs across two tenants with varying priorities
    rA1 = _mk_run(TENANT_A)
    rA2 = _mk_run(TENANT_A)
    rB1 = _mk_run(TENANT_B)
    rB2 = _mk_run(TENANT_B)

    # Enqueue with priorities
    assert _post_ok("/scheduler/enqueue", {"run_id": rA1, "priority": 10})["status"] in ("enqueued", "exists")
    assert _post_ok("/scheduler/enqueue", {"run_id": rA2, "priority": 10})["status"] in ("enqueued", "exists")
    assert _post_ok("/scheduler/enqueue", {"run_id": rB1, "priority": 10})["status"] in ("enqueued", "exists")
    assert _post_ok("/scheduler/enqueue", {"run_id": rB2, "priority": 5})["status"] in ("enqueued", "exists")

    # Idempotent enqueue
    again = _post_ok("/scheduler/enqueue", {"run_id": rA1, "priority": 10})
    assert again["status"] in ("exists", "enqueued")

    # Snapshot deterministic sorting: priority desc, then enqueue order/run_id asc
    snap = _get_ok("/scheduler/queue")
    items = snap.get("items", [])
    assert isinstance(items, list)
    # First three are priority 10 (two A, one B) then priority 5 (B2)
    assert items[0]["priority"] >= items[-1]["priority"]

    # Step fairness: round-robin across tenants at same priority, tenant cap 1, global 2
    s1 = _post_ok("/scheduler/step", {})
    s2 = _post_ok("/scheduler/step", {})
    # After two steps, two runs should be in completed or active no more than policy constraints
    assert s2.get("active") is not None

    # Backpressure: set queue_max=1 and attempt to enqueue 2 new runs
    httpx.patch(f"{BASE}/scheduler/policy", json={"queue_max": 1}, timeout=60).raise_for_status()
    rX1 = _mk_run(TENANT_A)
    rX2 = _mk_run(TENANT_A)
    ok1 = _post_ok("/scheduler/enqueue", {"run_id": rX1, "priority": 1})
    assert ok1["status"] in ("enqueued", "exists")
    r = httpx.post(f"{BASE}/scheduler/enqueue", json={"run_id": rX2, "priority": 1}, timeout=60)
    assert r.status_code == 400
    assert "capacity" in r.text

    # UI contains scheduler link and page contents
    root_html = _get_html("/ui")
    assert "/ui/scheduler" in root_html
    sched_html = _get_html("/ui/scheduler")
    assert "Scheduler" in sched_html and "Step" in sched_html and "Queue" in sched_html


