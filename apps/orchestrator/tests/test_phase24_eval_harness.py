import os, json, subprocess, sys, pathlib, shutil


def _python_bin() -> str:
    return ".venv/bin/python" if pathlib.Path(".venv/bin/python").exists() else sys.executable


def test_golden_discovery_and_determinism(tmp_path):
    base = pathlib.Path.cwd()
    eval_dir = base / "eval"
    report_path = eval_dir / "report.json"
    history_path = eval_dir / "history.json"

    # Clean previous outputs for isolation
    if eval_dir.exists():
        shutil.rmtree(eval_dir)

    env = os.environ.copy()
    env.update({
        "EVAL_ENABLED": "1",
        "EVAL_OUTDIR": str(eval_dir),
        "EVAL_INCLUDE": "",  # all
        "EVAL_EXCLUDE": "",
        "EVAL_THRESHOLD": "0.9",
        "EVAL_WRITE_KB": "0",
    })

    code1 = subprocess.call([_python_bin(), "scripts/eval_run.py"], env=env)
    assert code1 == 0
    assert report_path.exists()
    rep1 = json.loads(report_path.read_text(encoding="utf-8"))
    # Stable keys and structure
    assert set(rep1.keys()) == {"suites", "summary"}
    suites = rep1["suites"]
    assert isinstance(suites, list) and len(suites) >= 2
    # Sorted by id
    ids = [s["id"] for s in suites]
    assert ids == sorted(ids)
    # Timestamps present and string
    assert isinstance(rep1["summary"].get("started_at"), str)
    assert isinstance(rep1["summary"].get("finished_at"), str)

    # History update
    codeh = subprocess.call([_python_bin(), "scripts/eval_history.py"], env=env)
    assert codeh == 0
    assert history_path.exists()
    hist1 = json.loads(history_path.read_text(encoding="utf-8"))
    assert isinstance(hist1.get("runs"), list)

    # Re-run should be idempotent (same report and same history)
    code2 = subprocess.call([_python_bin(), "scripts/eval_run.py"], env=env)
    assert code2 == 0
    rep2 = json.loads(report_path.read_text(encoding="utf-8"))
    assert rep2 == rep1
    codeh2 = subprocess.call([_python_bin(), "scripts/eval_history.py"], env=env)
    hist2 = json.loads(history_path.read_text(encoding="utf-8"))
    assert hist2 == hist1


def test_threshold_gating(tmp_path):
    base = pathlib.Path.cwd()
    eval_dir = base / "eval"
    gold_dir = base / "eval" / "golden"
    gold_dir.mkdir(parents=True, exist_ok=True)
    # Add a temporary failing suite
    failing = {
        "id": "test-fail-suite",
        "version": "0.0.0",
        "tasks": [
            {"id": "force_fail", "category": "sanity", "weight": 1.0,
             "asserts": [
                 {"type": "file_json_eq", "file": "blueprints/web-crud-fastapi-postgres-react.json", "path": "id", "expect": "WRONG"}
             ]}
        ]
    }
    tmp_suite_path = gold_dir / "test-fail-suite.json"
    tmp_suite_path.write_text(json.dumps(failing, sort_keys=True) + "\n", encoding="utf-8")

    try:
        env = os.environ.copy()
        env.update({
            "EVAL_ENABLED": "1",
            "EVAL_OUTDIR": str(eval_dir),
            "EVAL_INCLUDE": "test-fail-suite",
            "EVAL_THRESHOLD": "1.0",
        })
        # Run wrapper -> should fail due to suite score 0 < 1.0
        code_bad = subprocess.call(["bash", "scripts/eval_check.sh"], env=env)
        assert code_bad == 1

        # Lower threshold to allow pass
        env["EVAL_THRESHOLD"] = "0.0"
        code_ok = subprocess.call(["bash", "scripts/eval_check.sh"], env=env)
        assert code_ok == 0
    finally:
        try:
            tmp_suite_path.unlink()
        except Exception:
            pass


def test_optional_kb_ingestion_offline(tmp_path):
    # Enable KB ingestion and ensure no exceptions and report remains present
    base = pathlib.Path.cwd()
    eval_dir = base / "eval"
    env = os.environ.copy()
    env.update({
        "EVAL_ENABLED": "1",
        "EVAL_OUTDIR": str(eval_dir),
        "EVAL_WRITE_KB": "1",
        # Deterministic IDs to reuse local sqlite
        "TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "PROJECT_ID": "00000000-0000-0000-0000-000000000000",
        # Ensure local-only behavior; ORCH_BASE not used in-process
    })
    code = subprocess.call([_python_bin(), "scripts/eval_run.py"], env=env)
    assert code == 0
    assert (eval_dir / "report.json").exists()

def test_outputs_newline_terminated():
    base = pathlib.Path.cwd()
    eval_dir = base / "eval"
    env = os.environ.copy()
    env.update({"EVAL_ENABLED": "1", "EVAL_OUTDIR": str(eval_dir)})
    subprocess.check_call([_python_bin(), "scripts/eval_run.py"], env=env)
    subprocess.check_call([_python_bin(), "scripts/eval_history.py"], env=env)
    rep_text = (eval_dir / "report.json").read_text(encoding="utf-8")
    hist_text = (eval_dir / "history.json").read_text(encoding="utf-8")
    assert rep_text.endswith("\n")
    assert hist_text.endswith("\n")


