import os, json, subprocess, sys, pathlib, shutil


def _python_bin() -> str:
    return ".venv/bin/python" if pathlib.Path(".venv/bin/python").exists() else sys.executable


def test_iac_plan_apply_determinism(tmp_path):
    base = pathlib.Path.cwd()
    iac_dir = base / "iac"
    plan_path = iac_dir / "plan.json"
    state_path = iac_dir / "state.json"

    # Clean previous outputs for isolation
    for p in (plan_path, state_path):
        try:
            p.unlink()
        except Exception:
            pass

    env = os.environ.copy()
    env.update({
        "IAC_ENABLED": "1",
        "IAC_ENV": "staging",
        "IAC_OUTDIR": str(iac_dir),
    })

    code1 = subprocess.call([_python_bin(), "scripts/iac_plan.py"], env=env)
    assert code1 == 0
    assert plan_path.exists()
    text1 = plan_path.read_text(encoding="utf-8")
    obj1 = json.loads(text1)
    assert set(obj1.keys()) == {"env", "modules", "version_pins"}
    assert text1.endswith("\n")

    # Re-run should be idempotent
    code2 = subprocess.call([_python_bin(), "scripts/iac_plan.py"], env=env)
    assert code2 == 0
    text2 = plan_path.read_text(encoding="utf-8")
    assert text2 == text1

    # Apply
    code3 = subprocess.call([_python_bin(), "scripts/iac_apply.py"], env=env)
    assert code3 == 0
    assert state_path.exists()
    state_text1 = state_path.read_text(encoding="utf-8")
    state_obj1 = json.loads(state_text1)
    assert set(state_obj1.keys()) == {"env", "resources", "status", "version_pins"}
    assert state_text1.endswith("\n")

    # Idempotent re-run
    code4 = subprocess.call([_python_bin(), "scripts/iac_apply.py"], env=env)
    assert code4 == 0
    state_text2 = state_path.read_text(encoding="utf-8")
    assert state_text2 == state_text1


def test_release_wrapper_gating(tmp_path):
    base = pathlib.Path.cwd()
    env = os.environ.copy()
    env.update({
        "IAC_ENABLED": "1",
        "IAC_ENV": "staging",
        "IAC_OUTDIR": str(base / "iac"),
        "RELEASE_ENABLED": "1",
        "RELEASE_ENV": "staging",
        "ROLL_OUT_STEPS": "10,50,100",
        "ROLL_OUT_THRESH_ERR": "0.02",
        "ROLL_OUT_THRESH_P95": "800",
    })

    # Bad fixture should fail
    env_bad = env.copy()
    env_bad["RELEASE_FIXTURES"] = "deployments/fixtures/canary_bad.json"
    code_bad = subprocess.call(["bash", "scripts/release_check.sh"], env=env_bad)
    assert code_bad != 0

    # OK fixture should pass
    env_ok = env.copy()
    env_ok["RELEASE_FIXTURES"] = "deployments/fixtures/canary_ok.json"
    code_ok = subprocess.call(["bash", "scripts/release_check.sh"], env=env_ok)
    assert code_ok == 0


def test_release_reporting_history_idempotent(tmp_path):
    base = pathlib.Path.cwd()
    dep_dir = base / "deployments"
    report_path = dep_dir / "report.json"
    history_path = dep_dir / "history.json"

    # Clean previous outputs
    for p in (report_path, history_path):
        try:
            p.unlink()
        except Exception:
            pass

    env = os.environ.copy()
    env.update({
        "RELEASE_ENABLED": "1",
        "RELEASE_ENV": "staging",
        "RELEASE_FIXTURES": "deployments/fixtures/canary_ok.json",
        "ROLL_OUT_STEPS": "10,50,100",
        "ROLL_OUT_THRESH_ERR": "0.02",
        "ROLL_OUT_THRESH_P95": "800",
    })

    code1 = subprocess.call([_python_bin(), "scripts/release_run.py"], env=env)
    assert code1 == 0
    assert report_path.exists()
    rep1 = json.loads(report_path.read_text(encoding="utf-8"))
    # Stable keys
    assert set(rep1.keys()) == {"env", "steps", "summary"}
    assert isinstance(rep1["steps"], list)
    assert isinstance(rep1["summary"].get("started_at"), str)
    assert isinstance(rep1["summary"].get("finished_at"), str)
    assert (dep_dir / "report.json").read_text(encoding="utf-8").endswith("\n")

    # History update
    codeh = subprocess.call([_python_bin(), "scripts/release_history.py"], env=env)
    assert codeh == 0
    assert history_path.exists()
    hist1 = json.loads(history_path.read_text(encoding="utf-8"))
    assert isinstance(hist1.get("runs"), list)
    assert (dep_dir / "history.json").read_text(encoding="utf-8").endswith("\n")

    # Re-run should be idempotent
    code2 = subprocess.call([_python_bin(), "scripts/release_run.py"], env=env)
    assert code2 == 0
    rep2 = json.loads(report_path.read_text(encoding="utf-8"))
    assert rep2 == rep1

    codeh2 = subprocess.call([_python_bin(), "scripts/release_history.py"], env=env)
    assert codeh2 == 0
    hist2 = json.loads(history_path.read_text(encoding="utf-8"))
    assert hist2 == hist1


def test_optional_kb_ingestion_offline_release(tmp_path):
    base = pathlib.Path.cwd()
    env = os.environ.copy()
    env.update({
        "RELEASE_ENABLED": "1",
        "RELEASE_ENV": "staging",
        "RELEASE_FIXTURES": "deployments/fixtures/canary_ok.json",
        "ROLL_OUT_STEPS": "10,50,100",
        "ROLL_OUT_THRESH_ERR": "0.02",
        "ROLL_OUT_THRESH_P95": "800",
        "RELEASE_WRITE_KB": "1",
        "TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "PROJECT_ID": "00000000-0000-0000-0000-000000000000",
    })
    code = subprocess.call([_python_bin(), "scripts/release_run.py"], env=env)
    assert code == 0
    assert (pathlib.Path("deployments") / "report.json").exists()
