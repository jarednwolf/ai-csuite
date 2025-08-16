import os
from fastapi.testclient import TestClient
from orchestrator.app import app


def test_scaffolder_dry_run_idempotent(tmp_path):
    # Ensure dry-run: no GitHub writes
    os.environ["GITHUB_WRITE_ENABLED"] = "0"
    client = TestClient(app)

    # Registry sanity
    r = client.get("/blueprints")
    assert r.status_code == 200
    assert any(b["id"] == "web-crud-fastapi-postgres-react" for b in r.json())

    body = {
        "blueprint_id": "web-crud-fastapi-postgres-react",
        "target": {"mode": "existing_repo", "owner": os.getenv("E2E_REPO_OWNER", ""), "name": os.getenv("E2E_REPO_NAME", ""), "default_branch": "main"},
        "run_id": "op-1234",
        "options": {},
    }

    # First run
    r1 = client.post("/app-factory/scaffold", json=body)
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    assert data1["blueprint"]["id"] == "web-crud-fastapi-postgres-react"
    assert data1["dry_run"] is True
    steps1 = data1["steps"]
    assert [s[0] for s in steps1] == [
        "init_repo_or_branch",
        "create_backend_service",
        "create_frontend_app",
        "db_migrations_and_seed",
        "wire_ci_cd_and_iac",
        "add_e2e_tests",
        "open_pr_and_request_gates",
    ]
    # Simulated statuses include preview placeholder
    ctxs = {s["context"] for s in data1["staged_statuses"]}
    assert "ai-csuite/preview-smoke" in ctxs

    # Re-run should be idempotent (no duplicate ledger rows; same successful response)
    r2 = client.post("/app-factory/scaffold", json=body)
    assert r2.status_code == 200
    data2 = r2.json()
    assert [s[0] for s in data2["steps"]] == [s[0] for s in steps1]
    assert data2["dry_run"] is True

    # Negative: Unknown blueprint
    bad = client.post(
        "/app-factory/scaffold",
        json={"blueprint_id": "does-not-exist", "target": {"mode": "existing_repo", "owner": "x", "name": "y"}},
    )
    assert bad.status_code == 404

    # Inject failure on one step; should raise 400 from endpoint with detail
    body_fail = dict(body)
    body_fail["run_id"] = "op-1235"
    body_fail["options"] = {"inject_fail_step": "create_backend_service"}
    r3 = client.post("/app-factory/scaffold", json=body_fail)
    assert r3.status_code == 400


