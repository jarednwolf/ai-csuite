import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_ROOT))
    out, err = p.communicate(timeout=60)
    return p.returncode, out.decode(), err.decode()


def python_bin() -> str:
    venv_py = REPO_ROOT / ".venv/bin/python"
    return str(venv_py) if venv_py.exists() else "python3"


def test_lockfiles_generated_and_idempotent(tmp_path):
    env = os.environ.copy()
    env["SUPPLY_CHAIN_ENABLED"] = "1"

    rc, out, err = run_cmd(["bash", "scripts/supply_chain_check.sh"])
    assert rc == 0, f"supply_chain_check failed: {out}\n{err}"

    orch_lock = REPO_ROOT / "apps/orchestrator/requirements.lock.txt"
    dev_lock = REPO_ROOT / "requirements-dev.lock.txt"
    assert orch_lock.exists(), "orchestrator lockfile missing"
    assert dev_lock.exists(), "dev lockfile missing"

    # Verify format: sorted, name==version only
    orch_lines = [l.strip() for l in orch_lock.read_text().splitlines() if l.strip()]
    assert orch_lines == sorted(orch_lines)
    assert all(re.match(r"^[a-z0-9_.\-]+==[^\s#]+$", l) for l in orch_lines)

    # Idempotency: re-run produces identical content
    before = orch_lock.read_text()
    rc2, out2, err2 = run_cmd(["bash", "scripts/supply_chain_check.sh"])
    assert rc2 == 0, f"second run failed: {out2}\n{err2}"
    after = orch_lock.read_text()
    assert before == after


def test_sbom_contains_expected_keys():
    # Ensure SBOM generated using project venv when available
    rc_gen, out_gen, err_gen = run_cmd([python_bin(), "scripts/sbom_gen.py"])
    assert rc_gen == 0, f"sbom_gen failed: {out_gen}\n{err_gen}"
    sbom_path = REPO_ROOT / "sbom/orchestrator-packages.json"
    assert sbom_path.exists(), "SBOM not generated"
    data = json.loads(sbom_path.read_text())
    assert "metadata" in data and "packages" in data
    assert isinstance(data["packages"], list)
    # Should include core deps like fastapi or sqlalchemy if installed
    names = {p.get("name", "").lower() for p in data["packages"]}
    assert any(n in names for n in {"fastapi", "sqlalchemy"}), "core packages not present in SBOM"


def test_license_check_default_allowlist_passes():
    # Generate report fresh to be deterministic
    rc, out, err = run_cmd([python_bin(), "scripts/license_check.py"])
    assert rc == 0, f"license check failed: {out}\n{err}"
    lic_report = REPO_ROOT / "sbom/licenses.json"
    assert lic_report.exists(), "license report missing"
    report = json.loads(lic_report.read_text())
    assert "packages" in report


def test_license_check_can_fail_with_restricted_allowlist():
    env = os.environ.copy()
    env["LICENSE_ALLOWLIST"] = "MIT"  # Intentionally too strict
    p = subprocess.Popen([python_bin(), "scripts/license_check.py"], cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(timeout=60)
    rc = p.returncode
    assert rc != 0, "license check should fail under strict allowlist"
    assert b"violations detected" in err


def test_dockerfiles_pinned_and_python_version_consistent():
    py_ver = (REPO_ROOT / ".python-version").read_text().strip()
    paths = [
        REPO_ROOT / "apps/orchestrator/Dockerfile",
        REPO_ROOT / "apps/worker/Dockerfile",
    ]
    for pth in paths:
        content = pth.read_text()
        m = re.search(r"^FROM\s+python:([^\s]+)", content, flags=re.MULTILINE)
        assert m, f"FROM not found in {pth}"
        tag = m.group(1)
        assert tag != "latest" and re.match(r"^[0-9]+\.[0-9]+\.[0-9]+(-slim)?$", tag), f"Unpinned tag in {pth}: {tag}"
        assert tag.startswith(py_ver), f"Dockerfile {pth} tag {tag} does not match .python-version {py_ver}"


