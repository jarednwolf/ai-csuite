import os, uuid, httpx, pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"


def _post_raw(p, j):
    return httpx.post(f"{BASE}{p}", json=j, timeout=60)


def _post_ok(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_ok(p):
    r = httpx.get(f"{BASE}{p}", timeout=60)
    r.raise_for_status()
    return r.json()


@pytest.mark.e2e
def test_phase11_retry_exhaust():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG11E-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG11 Exhaust"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    resp = _post_raw(
        f"/runs/{run['id']}/graph/start",
        {"force_qa_fail": False, "max_qa_loops": 2, "inject_failures": {"design": 5}},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["status"] == "failed"
    assert body["detail"]["failed_step"] == "design"
    assert body["detail"]["attempts"] == 3

    hist = _get_ok(f"/runs/{run['id']}/graph/history")
    # Should include product success, then three design error attempts, and nothing afterward
    names = [h["step_name"] for h in hist]
    statuses = [h["status"] for h in hist]
    attempts = [h["attempt"] for h in hist if h["step_name"] == "design"]
    assert names[0] == "product" and statuses[0] == "ok"
    assert names[1:4] == ["design", "design", "design"]
    assert statuses[1:4] == ["error", "error", "error"]
    assert attempts == [1, 2, 3]
    assert not any(n in names for n in ["research", "cto_plan", "engineer", "qa", "release"])


