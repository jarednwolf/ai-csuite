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
def test_graph_backtracks_on_qa_failure_then_passes():
    proj = _post("/projects", {"tenant_id": TENANT, "name": f"LGF-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG Backtrack"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    res = _post(f"/runs/{run['id']}/graph/start", {"force_qa_fail": True, "max_qa_loops": 2})
    assert res["status"] == "completed"
    assert res["tests_result"].get("passed") is True
    assert res["qa_attempts"] == 2

    st = _get(f"/runs/{run['id']}/graph/state")
    seq = st.get("history", [])
    # Engineer and QA must appear twice due to backtrack
    assert seq.count("engineer") == 2
    assert seq.count("qa") == 2
    assert seq[-1] == "release"


