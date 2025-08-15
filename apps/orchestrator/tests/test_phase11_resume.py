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

def _post_raw(p, j):
    return httpx.post(f"{BASE}{p}", json=j, timeout=60)


@pytest.mark.e2e
def test_phase11_resume():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG11R-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG11 Resume"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # Start but stop after research to simulate partial progress
    res1 = _post_ok(
        f"/runs/{run['id']}/graph/start",
        {"force_qa_fail": False, "max_qa_loops": 2, "stop_after": "research"},
    )
    assert res1["status"] == "completed"

    # History should show steps through research only
    hist1 = _get_ok(f"/runs/{run['id']}/graph/history")
    names1 = [h["step_name"] for h in hist1]
    assert names1 == ["product", "design", "research"]

    # Resume with no changes should complete remaining steps deterministically
    res2 = _post_ok(f"/runs/{run['id']}/graph/resume", {})
    assert res2["status"] == "completed"
    assert res2["tests_result"].get("passed") is True

    hist2 = _get_ok(f"/runs/{run['id']}/graph/history")
    names2 = [h["step_name"] for h in hist2]
    assert names2 == ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]



@pytest.mark.e2e
def test_phase11_resume_nothing_left_returns_400():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG11RN-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG11 Resume None"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # Complete full graph
    res = _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})
    assert res["status"] == "completed"

    # Resume should report nothing to do
    r2 = _post_raw(f"/runs/{run['id']}/graph/resume", {})
    assert r2.status_code == 400
    body = r2.json()
    assert body["detail"]["error"] == "Nothing to resume"


@pytest.mark.e2e
def test_phase11_resume_twice_after_completion_returns_400():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG11RT-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG11 Resume Twice"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # Stop early
    res1 = _post_ok(
        f"/runs/{run['id']}/graph/start",
        {"force_qa_fail": False, "max_qa_loops": 2, "stop_after": "research"},
    )
    assert res1["status"] == "completed"

    # First resume completes
    res2 = _post_ok(f"/runs/{run['id']}/graph/resume", {})
    assert res2["status"] == "completed"

    # Second resume should be 400
    r3 = _post_raw(f"/runs/{run['id']}/graph/resume", {})
    assert r3.status_code == 400
    body3 = r3.json()
    assert body3["detail"]["error"] == "Nothing to resume"

