from fastapi.testclient import TestClient
import json, os

from orchestrator.app import app


def test_ui_has_create_from_blueprint_nav_and_blueprints_page():
    client = TestClient(app)

    # /ui contains link text
    r = client.get("/ui")
    assert r.status_code == 200, r.text
    html = r.text
    assert "Create from Blueprint" in html

    # /ui/blueprints renders select and fields
    r2 = client.get("/ui/blueprints")
    assert r2.status_code == 200, r2.text
    html2 = r2.text
    assert "<select id=\"bpSelect\">" in html2 or "id=\"bpSelect\"" in html2
    # Required form fields
    for field in ("owner", "repo", "branch"):
        assert f"id=\"{field}\"" in html2


def test_scaffold_endpoint_dry_run_and_shape_offline():
    client = TestClient(app)
    # Pick a known blueprint id from repo manifests
    bp = "web-crud-fastapi-postgres-react"
    body = {
        "blueprint_id": bp,
        "target": {"mode": "existing_repo", "owner": None, "name": None, "default_branch": "main"},
        # run_id omitted to allow service to generate or reuse
    }
    prev = os.environ.get("GITHUB_WRITE_ENABLED")
    os.environ["GITHUB_WRITE_ENABLED"] = "0"
    try:
        r = client.post("/app-factory/scaffold", json=body)
    finally:
        if prev is None:
            del os.environ["GITHUB_WRITE_ENABLED"]
        else:
            os.environ["GITHUB_WRITE_ENABLED"] = prev
    assert r.status_code == 200, r.text
    data = r.json()
    # Response shape
    assert data.get("blueprint", {}).get("id") == bp
    assert isinstance(data.get("op_id"), str)
    assert "steps" in data and isinstance(data["steps"], list)
    # No network calls required; dry_run flag may be true/false depending on env, but endpoint is local-only
    assert "staged_statuses" in data


def test_run_budget_controls_compute_and_snapshot():
    client = TestClient(app)
    # Create minimal project/item/run
    proj = client.post("/projects", json={
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "name": "P27",
        "description": "",
        "repo_url": ""
    })
    assert proj.status_code == 200, proj.text
    project_id = proj.json()["id"]

    item = client.post("/roadmap-items", json={
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "project_id": project_id,
        "title": "P27 Budget"
    })
    assert item.status_code == 200, item.text
    item_id = item.json()["id"]

    run = client.post("/runs", json={
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "project_id": project_id,
        "roadmap_item_id": item_id,
        "phase": "delivery"
    })
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]

    # Run page includes Compute Budget control markup
    ui = client.get(f"/ui/run/{run_id}")
    assert ui.status_code == 200, ui.text
    assert "Compute Budget" in ui.text

    # Compute budget with deterministic defaults
    comp = client.post(f"/integrations/budget/{run_id}/compute", json={
        "warn_pct": 0.8,
        "block_pct": 1.0,
        "rate": {"usd_per_1k_tokens": 0.01}
    })
    assert comp.status_code == 200, comp.text
    snap = client.get(f"/integrations/budget/{run_id}")
    assert snap.status_code == 200, snap.text
    data = snap.json()
    assert data.get("run_id") == run_id
    assert "totals" in data and "status" in data


