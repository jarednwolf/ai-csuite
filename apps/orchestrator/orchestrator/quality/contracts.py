from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


def _exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except Exception:
        return False


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def compute_contract_coverage(db: Session, *, tenant_id: Optional[str], project_id: Optional[str], run_id: Optional[str], seed: int = 123) -> Dict[str, Any]:
    """
    Offline/deterministic contract coverage over local repo artifacts.
    Signals considered:
      - artifact schemas exist in `apps/orchestrator/orchestrator/artifacts/schemas/*.schema.json`
      - docs in `docs/*.md` exist
      - policy files present (`docs/PATCH_POLICY.md`, `docs/CHANGE_RISK_MATRIX.json`)
      - tests present for phases (apps/orchestrator/tests/test_phase*.py)
    Output keys sorted; newline-terminated when written by caller.
    """
    base = os.getcwd()
    schemas_dir = os.path.join("apps", "orchestrator", "orchestrator", "artifacts", "schemas")
    docs_dir = "docs"
    tests_dir = os.path.join("apps", "orchestrator", "tests")

    # Schemas
    schemas = []
    try:
        entries = sorted(os.listdir(schemas_dir))
    except Exception:
        entries = []
    for name in entries:
        if name.endswith(".schema.json"):
            schemas.append(name)

    # Docs signals
    required_docs = [
        "AI-CSUITE_HANDOFF.md",
        "AGENT_OPERATING_MANUAL.md",
        "CURSOR_BEST_PRACTICES.md",
        "PHASE_TRACKING_CHECKLIST.md",
        "SELF_DEV_AUTOPILOT.md",
        "PATCH_POLICY.md",
        "CHANGE_RISK_MATRIX.json",
    ]
    docs_status = {d: _exists(os.path.join(docs_dir, d)) for d in required_docs}

    # Tests
    try:
        test_files = sorted([f for f in os.listdir(tests_dir) if f.startswith("test_phase") and f.endswith(".py")])
    except Exception:
        test_files = []

    coverage = {
        "version": 1,
        "seed": int(seed),
        "schemas_present": sorted(schemas),
        "docs_present": {k: bool(v) for k, v in sorted(docs_status.items(), key=lambda kv: kv[0])},
        "tests_present": sorted(test_files),
        "project_id": project_id or "",
        "run_id": run_id or "",
    }
    # Derived scores (simple ratios for determinism)
    total_docs = len(required_docs)
    docs_ok = sum(1 for k in required_docs if docs_status.get(k))
    coverage["scores"] = {
        "docs": (docs_ok / total_docs) if total_docs else 0.0,
        "schemas": (len(schemas) / max(1, len(schemas))) if schemas else 0.0,
        "tests": (len(test_files) / max(1, len(test_files))) if test_files else 0.0,
    }
    return coverage


