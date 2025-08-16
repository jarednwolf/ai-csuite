import os, json, uuid, httpx, tempfile, pathlib, subprocess, sys

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")
TENANT = "00000000-0000-0000-0000-000000000000"


def _post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _get(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_secrets_scanner_local_and_deterministic(tmp_path):
    base = pathlib.Path.cwd()
    comp_dir = base / "compliance"
    comp_dir.mkdir(exist_ok=True)
    # Create rules
    rules = [
        {
            "id": "gh_pat",
            "category": "secret",
            "severity": "block",
            "description": "GitHub PAT",
            "pattern": "ghp_[A-Za-z0-9]{20,}",
            "redaction": "ghp_<redacted>",
        }
    ]
    (comp_dir / "regexes.json").write_text(json.dumps(rules, sort_keys=True) + "\n", encoding="utf-8")

    # Create temp file with a secret and a benign high-entropy string
    test_file = tmp_path / "sample.txt"
    test_file.write_text("this is fine abcdefghijklmnopqrstuvwxyz\nsecret ghp_123456789012345678901234\nR4nd0mL00k1ngButHarmless\n", encoding="utf-8")

    # Run scanner limited to tmp_path
    out_path = comp_dir / "secrets_report.json"
    code = subprocess.call([sys.executable, "scripts/secrets_scan.py", "--root", str(tmp_path), "--rules", str(comp_dir / "regexes.json"), "--out", str(out_path)])
    assert code != 0, "should fail on block finding"
    # Deterministic content
    rep = json.loads(out_path.read_text(encoding="utf-8"))
    # Only one finding; excerpt must be masked
    assert len(rep) == 1
    item = list(rep.values())[0]
    assert item["severity"] == "block"
    assert "ghp_<redacted>" in item["excerpt"] and "ghp_123" not in item["excerpt"]

    # Re-run should be identical
    code2 = subprocess.call([sys.executable, "scripts/secrets_scan.py", "--root", str(tmp_path), "--rules", str(comp_dir / "regexes.json"), "--out", str(out_path)])
    assert code2 != 0
    rep2 = json.loads(out_path.read_text(encoding="utf-8"))
    assert rep2 == rep


def test_redaction_vectors_and_determinism(tmp_path):
    base = pathlib.Path.cwd()
    comp_dir = base / "compliance"
    comp_dir.mkdir(exist_ok=True)
    vectors = [
        {"id": "email", "input": "Contact me at a@b.com", "expect_strict": "Contact me at <email:redacted>", "expect_relaxed": "Contact me at <email:redacted>"},
        {"id": "cc", "input": "Card 4242 4242 4242 4242 ok", "expect_strict": "Card <cc:redacted> ok", "expect_relaxed": "Card <cc:redacted> ok"},
        {"id": "name", "input": "Hello John Smith", "expect_strict": "Hello <name:redacted>", "expect_relaxed": "Hello John Smith"},
        {"id": "ssn", "input": "SSN 123-45-6789", "expect_strict": "SSN <ssn:redacted>", "expect_relaxed": "SSN <ssn:redacted>"},
    ]
    (comp_dir / "test_vectors.json").write_text(json.dumps(vectors, sort_keys=True) + "\n", encoding="utf-8")

    code = subprocess.call([sys.executable, "scripts/redaction_test_vectors.py"]) 
    assert code == 0
    rep = json.loads((comp_dir / "redaction_report.json").read_text(encoding="utf-8"))
    # All vectors should pass
    for v in vectors:
        r = rep[str(v["id"])]
        assert r["ok_strict"] and r["ok_relaxed"]

    # Idempotent
    code2 = subprocess.call([sys.executable, "scripts/redaction_test_vectors.py"]) 
    rep2 = json.loads((comp_dir / "redaction_report.json").read_text(encoding="utf-8"))
    assert rep2 == rep


def test_audit_logging_for_key_flows():
    # Create minimal project + run
    proj = _post("/projects", {"tenant_id": TENANT, "name": f"P-{uuid.uuid4().hex[:6]}", "description": "p", "repo_url": "https://github.com/test/test.git"})
    item = _post("/roadmap-items", {"tenant_id": TENANT, "project_id": proj["id"], "title": "T1"})
    run = _post("/runs", {"tenant_id": TENANT, "project_id": proj["id"], "roadmap_item_id": item["id"], "phase": "delivery"})

    # Budget compute
    _post(f"/integrations/budget/{run['id']}/compute", {"warn_pct": 0.8, "block_pct": 1.0})
    # Preview deploy + smoke (dry-run gh is fine)
    _post(f"/integrations/preview/{run['id']}/deploy", {"owner": "o", "repo": "r", "branch": "b"})
    _post(f"/integrations/preview/{run['id']}/smoke", {"timeout_ms": 10, "inject_fail": False})

    # GitHub approve/merge will be dry-run gated by env; endpoints still exercise audit paths
    try:
        httpx.post(f"{BASE}/integrations/github/pr/{run['id']}/approve", timeout=60)
    except Exception:
        pass
    try:
        httpx.post(f"{BASE}/integrations/github/pr/{run['id']}/merge", params={"method": "squash"}, timeout=60)
    except Exception:
        pass

    # Verify audit report script
    code = subprocess.call([sys.executable, "scripts/audit_verify.py"]) 
    rep = json.loads((pathlib.Path("compliance") / "audit_report.json").read_text(encoding="utf-8"))
    assert isinstance(rep.get("rows"), list)
    # At least one of required events should be present
    got_types = {r["event_type"] for r in rep.get("rows", [])}
    assert len(got_types & {"budget.compute", "preview.deploy", "preview.smoke", "github.approve", "github.merge"}) >= 1


def test_compliance_script_wrapper():
    # Ensure vectors and rules in place
    base = pathlib.Path.cwd()
    comp_dir = base / "compliance"
    if not (comp_dir / "regexes.json").exists():
        (comp_dir / "regexes.json").write_text(json.dumps([], sort_keys=True) + "\n", encoding="utf-8")
    if not (comp_dir / "test_vectors.json").exists():
        (comp_dir / "test_vectors.json").write_text(json.dumps([], sort_keys=True) + "\n", encoding="utf-8")
    code = subprocess.call(["bash", "scripts/compliance_check.sh"]) 
    assert code in (0, 1)


