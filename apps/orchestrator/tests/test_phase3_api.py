from fastapi.testclient import TestClient
from orchestrator.app import app

TENANT = "00000000-0000-0000-0000-000000000000"

def test_projects_roadmap_and_run_flow():
    client = TestClient(app)

    # Create a project
    p = client.post("/projects", json={
        "tenant_id": TENANT,
        "name": "Demo Project",
        "description": "desc",
        "repo_url": "https://example.com/repo.git"
    })
    assert p.status_code == 200, p.text
    project = p.json()
    assert project["id"]
    project_id = project["id"]

    # Create a roadmap item
    rmi = client.post("/roadmap-items", json={
        "tenant_id": TENANT,
        "project_id": project_id,
        "title": "First Feature",
        "description": "do a thing",
        "priority": 10
    })
    assert rmi.status_code == 200, rmi.text
    item_id = rmi.json()["id"]

    # Create a run
    run = client.post("/runs", json={
        "tenant_id": TENANT,
        "project_id": project_id,
        "roadmap_item_id": item_id,
        "phase": "delivery"
    })
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]

    # Start the run (agent skeleton should complete it)
    started = client.post(f"/runs/{run_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] in ("running","succeeded")

    # Fetch final state
    got = client.get(f"/runs/{run_id}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "succeeded"


