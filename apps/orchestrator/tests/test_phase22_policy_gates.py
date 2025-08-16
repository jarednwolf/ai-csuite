import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def python_bin() -> str:
    venv_py = REPO_ROOT / ".venv/bin/python"
    return str(venv_py) if venv_py.exists() else "python3"


def run_cmd(cmd: list[str], env: dict | None = None) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_ROOT), env=env)
    out, err = p.communicate(timeout=60)
    return p.returncode, out.decode(), err.decode()


def read_json(p: Path) -> dict:
    return json.loads(p.read_text())


def write_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def test_facts_generation_idempotent(tmp_path):
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    # Seed fixtures
    # Licenses: clean allowlist with no packages → no violations
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    # Required statuses: all success
    write_json(REPO_ROOT / "policy/statuses.json", {
        "statuses": [
            {"context": "ai-csuite/dor", "state": "success"},
            {"context": "ai-csuite/human-approval", "state": "success"},
            {"context": "ai-csuite/artifacts", "state": "success"},
            {"context": "ai-csuite/preview-smoke", "state": "success"}
        ]
    })
    # Licenses: reuse Phase 21 output (already present in repo)
    # Budget snapshot (ok)
    write_json(REPO_ROOT / "policy/budget_snapshot.json", {
        "status": "ok",
        "totals": {"pct_used": 0.25}
    })
    # DoR present
    write_json(REPO_ROOT / "policy/dor.json", {
        "prd": True, "design": True, "research": True, "acceptance_criteria": True
    })

    # First run
    rc1, out1, err1 = run_cmd([python_bin(), "scripts/policy_input_collect.py"] , env=env)
    assert rc1 == 0, f"collect failed: {out1}\n{err1}"
    facts_path = REPO_ROOT / "policy/facts.json"
    assert facts_path.exists()
    first = facts_path.read_text()

    # Second run should be identical
    rc2, out2, err2 = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc2 == 0, f"second collect failed: {out2}\n{err2}"
    second = facts_path.read_text()
    assert first == second, "facts not idempotent"


def _seed_all_green():
    write_json(REPO_ROOT / "policy/statuses.json", {
        "statuses": [
            {"context": "ai-csuite/dor", "state": "success"},
            {"context": "ai-csuite/human-approval", "state": "success"},
            {"context": "ai-csuite/artifacts", "state": "success"},
            {"context": "ai-csuite/preview-smoke", "state": "success"}
        ]
    })
    write_json(REPO_ROOT / "policy/budget_snapshot.json", {"status": "ok", "totals": {"pct_used": 0.2}})
    write_json(REPO_ROOT / "policy/dor.json", {"prd": True, "design": True, "research": True, "acceptance_criteria": True})


def test_policy_passes_when_gates_satisfied():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    _seed_all_green()
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    # Ensure facts present
    rc_c, _, err_c = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0, f"collect failed: {err_c}"
    # Evaluate
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc == 0, f"policy eval failed unexpectedly: {out}\n{err}"
    report = read_json(REPO_ROOT / "policy/report.json")
    assert report["status"] == "pass"


def test_policy_fails_on_missing_status():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    # Missing preview-smoke
    write_json(REPO_ROOT / "policy/statuses.json", {
        "statuses": [
            {"context": "ai-csuite/dor", "state": "success"},
            {"context": "ai-csuite/human-approval", "state": "success"},
            {"context": "ai-csuite/artifacts", "state": "success"}
        ]
    })
    write_json(REPO_ROOT / "policy/budget_snapshot.json", {"status": "ok", "totals": {"pct_used": 0.2}})
    write_json(REPO_ROOT / "policy/dor.json", {"prd": True, "design": True, "research": True, "acceptance_criteria": True})
    rc_c, _, err_c = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc != 0, "policy should fail on missing status"
    assert "Required contexts" in err


def test_policy_fails_on_license_violation(tmp_path):
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    # Force a fake violation by writing a minimal sbom/licenses.json with a disallowed license
    sbom_dir = REPO_ROOT / "sbom"
    sbom_dir.mkdir(exist_ok=True)
    write_json(sbom_dir / "licenses.json", {
        "allowlist": ["MIT"],
        "packages": [
            {"name": "badlib", "version": "1.0.0", "license": "GPL-3.0", "classifiers": []}
        ]
    })
    _seed_all_green()
    rc_c, _, _ = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc != 0, "policy should fail on license violation"
    assert "License violations" in err


def test_policy_fails_on_budget_block():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    _seed_all_green()
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    write_json(REPO_ROOT / "policy/budget_snapshot.json", {"status": "blocked", "totals": {"pct_used": 1.2}})
    rc_c, _, _ = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc != 0
    assert "Budget is in blocked state" in err


def test_policy_fails_on_dor_missing():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    _seed_all_green()
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    write_json(REPO_ROOT / "policy/dor.json", {"prd": True, "design": False, "research": True, "acceptance_criteria": False})
    rc_c, _, _ = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc != 0
    assert "DoR missing" in err


def test_warn_override_allows_passing():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    env["POLICY_ALLOW_WARN_OVERRIDE"] = "1"
    _seed_all_green()
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    # Put budget into warn state
    write_json(REPO_ROOT / "policy/budget_snapshot.json", {"status": "warn", "totals": {"pct_used": 0.85}})
    rc_c, _, _ = run_cmd([python_bin(), "scripts/policy_input_collect.py"], env=env)
    assert rc_c == 0
    rc, out, err = run_cmd([python_bin(), "scripts/policy_eval.py"], env=env)
    assert rc == 0, f"warn override should allow passing: {out}\n{err}"
    report = read_json(REPO_ROOT / "policy/report.json")
    assert report["status"] in {"pass", "warn"}


def test_policy_check_script_exit_codes():
    env = os.environ.copy()
    env["POLICY_ENABLED"] = "1"
    _seed_all_green()
    write_json(REPO_ROOT / "sbom/licenses.json", {
        "allowlist": [
            "MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC", "PSF", "MPL-2.0", "LGPL-3.0-or-later", "LGPL-2.1-or-later"
        ],
        "packages": []
    })
    # Clean case
    rc_ok, out_ok, err_ok = run_cmd(["bash", "scripts/policy_check.sh"], env=env)
    assert rc_ok == 0, f"policy_check.sh failed unexpectedly: {out_ok}\n{err_ok}"

    # Violating case: remove a required status
    write_json(REPO_ROOT / "policy/statuses.json", {
        "statuses": [
            {"context": "ai-csuite/dor", "state": "success"},
            {"context": "ai-csuite/human-approval", "state": "success"}
        ]
    })
    rc_bad, out_bad, err_bad = run_cmd(["bash", "scripts/policy_check.sh"], env=env)
    assert rc_bad != 0
    assert "Required contexts" in err_bad


