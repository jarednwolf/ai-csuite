import os, json, subprocess, sys, pathlib, shutil
from fastapi.testclient import TestClient
from orchestrator.app import app


def _python_bin() -> str:
    return ".venv/bin/python" if pathlib.Path(".venv/bin/python").exists() else sys.executable


def test_registry_and_api_include_new_manifests():
    c = TestClient(app)
    r = c.get("/blueprints")
    assert r.status_code == 200, r.text
    items = r.json()
    ids = sorted([i["id"] for i in items])
    # New manifests present
    assert "mobile-crud-expo-supabase" in ids
    assert "realtime-media-web" in ids

    # GET by id returns full manifest with expected fields
    r1 = c.get("/blueprints/mobile-crud-expo-supabase")
    assert r1.status_code == 200, r1.text
    mf1 = r1.json()
    assert mf1["stack"]["frontend"]["framework"] in ("expo", "react")
    assert isinstance(mf1["quality_gates"]["a11y_min"], int)
    assert isinstance(mf1["quality_gates"]["e2e_cov_min"], float)
    assert isinstance(mf1["quality_gates"]["perf_budget_ms"], int)

    r2 = c.get("/blueprints/realtime-media-web")
    assert r2.status_code == 200, r2.text
    mf2 = r2.json()
    assert mf2["stack"]["backend"]["framework"] == "fastapi"


def test_deterministic_report_and_idempotency(tmp_path):
    base = pathlib.Path.cwd()
    outdir = base / "blueprints"
    report_path = outdir / "report.json"
    # Remove report if exists to start clean
    if report_path.exists():
        report_path.unlink()

    env = os.environ.copy()
    env.update({
        "BLUEPRINTS_ENABLED": "1",
        "BLUEPRINTS_OUTDIR": str(outdir),
        "BLUEPRINTS_INCLUDE": "",
        "BLUEPRINTS_EXCLUDE": "",
        "BLUEPRINTS_WRITE_KB": "0",
    })

    code1 = subprocess.call([_python_bin(), "scripts/blueprints_report.py"], env=env)
    assert code1 == 0
    assert report_path.exists()
    rep1_text = report_path.read_text(encoding="utf-8")
    assert rep1_text.endswith("\n")
    rep1 = json.loads(rep1_text)
    assert set(rep1.keys()) == {"blueprints", "summary"}
    # Sorted by id
    ids = [b["id"] for b in rep1["blueprints"]]
    assert ids == sorted(ids)
    # Timestamps present
    assert isinstance(rep1["summary"].get("started_at"), str)
    assert isinstance(rep1["summary"].get("finished_at"), str)

    # Re-run should be idempotent
    code2 = subprocess.call([_python_bin(), "scripts/blueprints_report.py"], env=env)
    assert code2 == 0
    rep2_text = report_path.read_text(encoding="utf-8")
    assert rep2_text == rep1_text


def test_wrapper_exit_codes_and_fail_injection(tmp_path):
    base = pathlib.Path.cwd()
    outdir = base / "blueprints"
    report_path = outdir / "report.json"

    # Clean report
    if report_path.exists():
        report_path.unlink()

    # Happy path: should pass
    env = os.environ.copy()
    env.update({
        "BLUEPRINTS_ENABLED": "1",
        "BLUEPRINTS_OUTDIR": str(outdir),
    })
    ok = subprocess.call(["bash", "scripts/blueprints_check.sh"], env=env)
    assert ok == 0

    # Inject a failing manifest temporarily (invalid version)
    bad_path = base / "blueprints" / "_tmp_bad.json"
    bad = {
        "id": "tmp-fail",
        "version": "bad.version",
        "name": "Tmp Bad",
        "description": "",
        "stack": {
            "backend": {"runtime": "python3.12", "framework": "fastapi", "db": "postgres"},
            "frontend": {"framework": "react"},
            "infra": {"containers": True, "iac": "terraform", "preview_envs": True}
        },
        "capabilities": [],
        "quality_gates": {"a11y_min": 10, "e2e_cov_min": 0.1, "perf_budget_ms": 1000},
        "scaffold": [{"step": "init_repo_or_branch"}],
        "deploy_targets": ["preview"]
    }
    bad_path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
    try:
        env2 = os.environ.copy()
        env2.update({
            "BLUEPRINTS_ENABLED": "1",
            "BLUEPRINTS_OUTDIR": str(outdir),
            "BLUEPRINTS_INCLUDE": "*",
            "BLUEPRINTS_EXCLUDE": "",
        })
        code_bad = subprocess.call(["bash", "scripts/blueprints_check.sh"], env=env2)
        assert code_bad == 1
    finally:
        try:
            bad_path.unlink()
        except Exception:
            pass


