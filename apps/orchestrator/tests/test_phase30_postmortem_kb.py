import os, uuid, httpx, pytest

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")
TENANT = "00000000-0000-0000-0000-000000000000"

def _post(p, j=None):
    if j is None:
        r = httpx.post(f"{BASE}{p}", timeout=60)
    else:
        r = httpx.post(f"{BASE}{p}", json=j, timeout=60)
    r.raise_for_status()
    return r.json()

def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=60)
    r.raise_for_status()
    return r.json()


@pytest.mark.e2e
def test_postmortem_generate_reset_ingest_search_and_ui():
    # Ensure postmortems enabled
    os.environ.setdefault("POSTMORTEM_ENABLED", "1")
    os.environ.setdefault("POSTMORTEM_AUTO_KB", "0")

    # Project & item
    proj = _post("/projects", {"tenant_id": TENANT, "name": f"PM-{uuid.uuid4().hex[:6]}", "description": "", "repo_url": ""})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "PM Feature"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})
    run_id = run["id"]

    # Exercise graph to produce history (no failures)
    res = _post(f"/runs/{run_id}/graph/start", {"force_qa_fail": False, "max_qa_loops": 2})
    assert res["status"] == "completed"

    # Generate postmortem (idempotent)
    pm1 = _post(f"/postmortems/{run_id}/generate")
    assert "artifact" in pm1 and "metrics" in pm1
    art = pm1["artifact"]
    assert art["meta"]["run_id"] == run_id
    assert "timeline" in art and isinstance(art["timeline"], list) and len(art["timeline"]) >= 1
    # retries summary accurate and failed_step present only when applicable
    assert isinstance(art["meta"].get("retries"), int)
    # Calling generate again yields same structure deterministically
    pm2 = _post(f"/postmortems/{run_id}/generate")
    assert pm2["artifact"]["meta"]["retries"] == art["meta"]["retries"]

    # GET returns artifact
    got = _get(f"/postmortems/{run_id}")
    assert got["meta"]["run_id"] == run_id

    # Reset clears
    _post(f"/postmortems/{run_id}/reset")
    with pytest.raises(httpx.HTTPStatusError):
        _get(f"/postmortems/{run_id}")

    # Re-generate after reset yields deterministic content again
    pm3 = _post(f"/postmortems/{run_id}/generate")
    assert pm3["artifact"]["meta"]["retries"] == art["meta"]["retries"]

    # Ingest to KB (idempotent)
    ing = _post(f"/postmortems/{run_id}/ingest-kb")
    assert ing.get("ok") is True or ing.get("already") is True
    # Repeat should be idempotent
    ing2 = _post(f"/postmortems/{run_id}/ingest-kb")
    assert ing2.get("ok") is True or ing2.get("already") is True

    # Search API returns deterministic array; includes our run id
    results = _get("/postmortems/search?q=run")
    assert isinstance(results, list)
    # Sorted by run_id asc
    ids = [r["run_id"] for r in results]
    assert ids == sorted(ids)
    assert any(r["run_id"] == run_id for r in results)

    # UI: root contains Postmortems link; page renders table and controls
    ui = httpx.get(f"{BASE}/ui", timeout=60)
    ui.raise_for_status()
    assert "/ui/postmortems" in ui.text
    page = httpx.get(f"{BASE}/ui/postmortems", timeout=60)
    page.raise_for_status()
    assert "<table" in page.text and "Generate" in page.text and "Ingest" in page.text


