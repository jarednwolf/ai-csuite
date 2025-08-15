import os, uuid, httpx, pytest

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

@pytest.mark.e2e
def test_graph_happy_path():
    # Project with empty repo_url to avoid PR side-effects
    proj = _post("/projects", {"tenant_id": TENANT, "name": f"LG-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG Feature"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    res = _post(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})
    assert res["status"] == "completed"
    assert res["tests_result"].get("passed") is True
    assert res["qa_attempts"] == 1

    # State endpoint returns full state incl. history sequence
    st = _get(f"/runs/{run['id']}/graph/state")
    seq = st.get("history", [])
    assert seq == ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]


