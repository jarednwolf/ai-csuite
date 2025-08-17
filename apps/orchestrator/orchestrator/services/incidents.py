from __future__ import annotations

import os
import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import RunDB


def _write_json_sorted(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = json.dumps(data, sort_keys=True) + "\n"
    cur = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if content != cur:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def _inc_dir() -> str:
    return os.path.join("apps", "orchestrator", "orchestrator", "incidents")


class IncidentService:
    """
    Phase 60 — Self-healing (auto-revert & bisect).
    Offline deterministic simulator creating artifacts under incidents/.
    """

    def open_revert(self, db: Session, *, run_id: str, reason: str) -> Dict[str, Any]:
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")
        inc_id = str(uuid.uuid4())
        artifact = {
            "incident_id": inc_id,
            "type": "revert",
            "run_id": run_id,
            "reason": reason,
            "actions": [
                "revert_commit",
                "preview_smoke",
                "evals_run",
            ],
            "result": {
                "preview_smoke": "success",
                "evals": {"score": 1.0, "threshold": 0.9},
            },
        }
        path = os.path.join(_inc_dir(), f"revert-{inc_id}.json")
        _write_json_sorted(path, artifact)
        return {"incident_id": inc_id, "path": path, "status": "created"}

    def open_bisect(self, db: Session, *, run_id: str, start_sha: str, end_sha: str) -> Dict[str, Any]:
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")
        inc_id = str(uuid.uuid4())
        # Deterministic fake steps
        steps: List[Dict[str, Any]] = []
        shas = [start_sha, end_sha]
        for idx, sha in enumerate(sorted(shas)):
            steps.append({"sha": sha, "build": "ok", "smoke": "ok", "eval_score": 1.0 - (idx * 0.01)})
        culprit = sorted(shas)[-1]
        artifact = {
            "incident_id": inc_id,
            "type": "bisect",
            "run_id": run_id,
            "range": {"start": start_sha, "end": end_sha},
            "steps": steps,
            "culprit": culprit,
        }
        path = os.path.join(_inc_dir(), f"bisect-{inc_id}.json")
        _write_json_sorted(path, artifact)
        return {"incident_id": inc_id, "path": path, "status": "created"}


