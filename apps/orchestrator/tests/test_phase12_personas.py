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
def test_phase12_personas_happy_path():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG12-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG12 HP"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    res = _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})
    assert res["status"] == "completed"
    assert res["tests_result"].get("passed") is True

    # Inspect full state for artifacts and shared memory
    st = _get_ok(f"/runs/{run['id']}/graph/state")
    seq = st.get("history", [])
    assert seq == ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]

    # Persona artifacts
    prd = st.get("prd", {})
    assert isinstance(prd, dict) and prd.get("title")

    design = st.get("design", {})
    assert design.get("passes") is True
    assert isinstance(design.get("heuristics_score"), int)

    research = st.get("research", {})
    assert research.get("summary")
    assert isinstance(research.get("evidence"), list) and len(research.get("evidence")) >= 1

    plan = st.get("plan", {})
    assert isinstance(plan.get("tasks"), list) and len(plan.get("tasks")) >= 1

    # Shared memory assertions
    sm = st.get("shared_memory", {})
    notes = sm.get("notes", []) if isinstance(sm, dict) else []
    assert isinstance(notes, list) and len(notes) >= 3
    note_steps = {n.get("step") for n in notes if isinstance(n, dict)}
    assert {"product", "design", "research"}.issubset(note_steps)
    assert "release" in note_steps  # memory survives through release


@pytest.mark.e2e
def test_phase12_personas_resume_shared_memory_preserved():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG12R-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG12 Resume"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    # Start then pause after research
    res1 = _post_ok(
        f"/runs/{run['id']}/graph/start",
        {"force_qa_fail": False, "max_qa_loops": 2, "stop_after": "research"},
    )
    assert res1["status"] == "completed"

    hist1 = _get_ok(f"/runs/{run['id']}/graph/history")
    names1 = [h["step_name"] for h in hist1]
    assert names1 == ["product", "design", "research"]

    # Memory before resume
    st1 = _get_ok(f"/runs/{run['id']}/graph/state")
    sm1 = st1.get("shared_memory", {})
    notes1 = sm1.get("notes", []) if isinstance(sm1, dict) else []
    assert isinstance(notes1, list) and len(notes1) >= 3
    steps1 = {n.get("step") for n in notes1 if isinstance(n, dict)}
    assert {"product", "design", "research"}.issubset(steps1)

    # Resume to completion
    res2 = _post_ok(f"/runs/{run['id']}/graph/resume", {})
    assert res2["status"] == "completed"

    st2 = _get_ok(f"/runs/{run['id']}/graph/state")
    seq2 = st2.get("history", [])
    assert seq2[-1] == "release"
    sm2 = st2.get("shared_memory", {})
    notes2 = sm2.get("notes", []) if isinstance(sm2, dict) else []
    assert len(notes2) >= len(notes1)
    steps2 = {n.get("step") for n in notes2 if isinstance(n, dict)}
    # Ensure earlier memory remains and is accessible post-resume
    assert {"product", "design", "research"}.issubset(steps2)


@pytest.mark.e2e
def test_phase12_personas_backtrack_memory_intact():
    proj = _post_ok(
        "/projects",
        {"tenant_id": TENANT, "name": f"LG12B-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""},
    )
    item = _post_ok(
        "/roadmap-items",
        {"tenant_id": TENANT, "project_id": proj["id"], "title": "LG12 Backtrack"},
    )
    run = _post_ok(
        "/runs",
        {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"},
    )

    res = _post_ok(f"/runs/{run['id']}/graph/start", {"force_qa_fail": True, "max_qa_loops": 2})
    assert res["status"] == "completed"
    assert res["tests_result"].get("passed") is True
    assert res.get("qa_attempts") == 2

    st = _get_ok(f"/runs/{run['id']}/graph/state")
    seq = st.get("history", [])
    assert seq.count("engineer") == 2
    assert seq.count("qa") == 2
    assert seq[-1] == "release"

    # Memory should remain intact and include two QA entries
    sm = st.get("shared_memory", {})
    notes = sm.get("notes", []) if isinstance(sm, dict) else []
    qa_notes = [n for n in notes if isinstance(n, dict) and n.get("step") == "qa"]
    assert len(qa_notes) == 2


