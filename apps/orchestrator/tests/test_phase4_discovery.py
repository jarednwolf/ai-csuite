from fastapi.testclient import TestClient
from orchestrator.app import app

TENANT = "00000000-0000-0000-0000-000000000000"

def test_discovery_and_dor_gate():
    client = TestClient(app)

    # Create project
    p = client.post("/projects", json={
        "tenant_id": TENANT, "name": "P4 Project", "description": "", "repo_url": ""
    })
    assert p.status_code == 200, p.text
    project_id = p.json()["id"]

    # Create roadmap item
    rmi = client.post("/roadmap-items", json={
        "tenant_id": TENANT, "project_id": project_id, "title": "P4 Feature"
    })
    assert rmi.status_code == 200, rmi.text
    item_id = rmi.json()["id"]

    # Create run
    run = client.post("/runs", json={
        "tenant_id": TENANT, "project_id": project_id, "roadmap_item_id": item_id, "phase": "delivery"
    })
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]

    # Start run -> should auto-create discovery artifacts & pass DoR -> then succeed
    started = client.post(f"/runs/{run_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] in ("running","succeeded","blocked")
    # Fetch final state
    got = client.get(f"/runs/{run_id}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "succeeded"

    # Inspect discovery status
    disc = client.get(f"/roadmap-items/{item_id}/discovery")
    assert disc.status_code == 200, disc.text
    dj = disc.json()
    assert dj["dor_pass"] is True
    assert dj["prd"] is not None
    assert dj["design"] is not None
    assert dj["research"] is not None
    # PRD should have AC
    assert len(dj["prd"]["prd"]["acceptance_criteria"]) >= 1


