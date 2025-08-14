from fastapi.testclient import TestClient
from orchestrator.app import app

TENANT = "00000000-0000-0000-0000-000000000000"

def test_kb_and_discovery_rag():
    c = TestClient(app)

    # Project + item
    p = c.post("/projects", json={"tenant_id": TENANT, "name": "KB Project", "description": "", "repo_url": ""})
    assert p.status_code == 200, p.text
    proj_id = p.json()["id"]

    rmi = c.post("/roadmap-items", json={"tenant_id": TENANT, "project_id": proj_id, "title": "Speed Feature"})
    assert rmi.status_code == 200, rmi.text
    item_id = rmi.json()["id"]

    # Ingest some prior context
    text = "Speed Feature reduces task time by 20 percent for power users. Keyboard shortcuts are critical."
    ing = c.post("/kb/ingest", json={
        "tenant_id": TENANT, "project_id": proj_id, "kind": "note", "ref_id": "", "text": text
    })
    assert ing.status_code == 200, ing.text
    assert ing.json()["chunks"] >= 1

    # Search should retrieve something for 'Speed Feature'
    srch = c.get("/kb/search", params={"tenant_id": TENANT, "project_id": proj_id, "q": "Speed Feature", "k": 3})
    assert srch.status_code == 200, srch.text
    hits = srch.json()
    assert len(hits) >= 1

    # Create run -> start -> should succeed (discovery will use RAG)
    run = c.post("/runs", json={"tenant_id": TENANT, "project_id": proj_id, "roadmap_item_id": item_id, "phase": "delivery"})
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]

    started = c.post(f"/runs/{run_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] in ("running", "succeeded")

    got = c.get(f"/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["status"] == "succeeded"

    # Discovery status should include related results and PRD references
    disc = c.get(f"/roadmap-items/{item_id}/discovery")
    assert disc.status_code == 200
    dj = disc.json()
    assert dj["dor_pass"] is True
    assert isinstance(dj["related"], list) and len(dj["related"]) >= 1
    # PRD references present
    refs = dj["prd"]["prd"].get("references", [])
    assert isinstance(refs, list)


