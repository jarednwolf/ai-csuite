import os, uuid, httpx, pytest

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


@pytest.mark.e2e
def test_phase11_graph_happy_path():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG11-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG11 HP"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    res = _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})
    assert res["status"] == "completed"
    assert res["tests_result"].get("passed") is True
    assert res["qa_attempts"] == 1

    hist = _get_ok(f"/runs/{run['id']}/graph/history")
    assert len(hist) >= 7
    names = [h["step_name"] for h in hist]
    statuses = [h["status"] for h in hist]
    # Must include the canonical sequence of successful steps
    assert names[:7] == ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]
    assert all(s == "ok" for s in statuses[:7])


