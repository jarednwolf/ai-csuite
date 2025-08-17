from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EvalReportDB, LLMTrace
from ..providers.registry import registry


router = APIRouter()


class EvalsRunBody(BaseModel):
    run_id: Optional[str] = None
    bundle_id: str = "default"
    threshold: Optional[float] = None


def _read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json_sorted(path: str, data: Any) -> None:
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


@router.post("/evals/run")
def evals_run(body: EvalsRunBody, db: Session = Depends(get_db)):
    # Offline harness reuse: execute scripts/eval_run.py in-process via importlib
    import importlib.util, sys
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    script_path = os.path.join(repo_root, "scripts", "eval_run.py")
    spec = importlib.util.spec_from_file_location("eval_run", script_path)
    if spec is None or spec.loader is None:
        raise HTTPException(500, "failed to load eval harness")
    mod = importlib.util.module_from_spec(spec)
    # Ensure orchestrator package is importable from apps/orchestrator
    apps_dir = os.path.join(repo_root, "apps", "orchestrator")
    if apps_dir not in sys.path:
        sys.path.insert(0, apps_dir)
    spec.loader.exec_module(mod)  # type: ignore
    # Configure env overrides for deterministic output dir under repo root
    os.environ.setdefault("EVAL_OUTDIR", os.path.join(repo_root, "eval"))
    if body.threshold is not None:
        os.environ["EVAL_THRESHOLD"] = str(body.threshold)
    code = int(mod.main())  # type: ignore
    if code != 0:
        raise HTTPException(400, "eval harness failed")
    report = _read_json("eval/report.json") or {"suites": [], "summary": {"score": 0.0, "passed": 0, "failed": 0}}
    # Persist as append-only eval_reports
    row = EvalReportDB(id=str(uuid.uuid4()), bundle_id=body.bundle_id, report=report)
    db.add(row)
    # Record a trace id for observability (Phase 40)
    try:
        obs = registry()._build("llm_observability", "mock_llm_observability")  # ensure available even if not configured
        trace_id = obs.trace_start(body.run_id or "", {"action": "evals.run"})
        db.add(LLMTrace(id=str(uuid.uuid4()), run_id=body.run_id, trace_id=trace_id, meta={"action": "evals.run", "score": report.get("summary", {}).get("score", 0.0)}))
        obs.trace_stop(trace_id, {"result": "ok"})
    except Exception:
        pass
    db.commit()
    return {"status": "ok", "report": report}


@router.get("/evals/report")
def evals_report(db: Session = Depends(get_db)):
    # Return latest
    row = db.query(EvalReportDB).order_by(EvalReportDB.created_at.desc()).first()
    if not row:
        return {"suites": [], "summary": {"score": 0.0, "passed": 0, "failed": 0}}
    return row.report



