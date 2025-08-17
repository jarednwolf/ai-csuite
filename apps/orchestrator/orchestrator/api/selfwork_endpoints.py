from __future__ import annotations

import os
import json
import uuid
import random
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SpeculativeReport, AgentReview
from ..selfwork.speculate import run_speculation
from ..selfwork.review import run_agent_review
from ..providers.registry import registry
from ..security import audit_event
from .evals_endpoints import evals_run, EvalsRunBody
from .safety_endpoints import safety_moderate, ModerateBody


router = APIRouter(prefix="", tags=["self-work"])


class SelfDocsBody(BaseModel):
    title: str
    summary: str
    changes: Dict[str, str]  # path -> markdown delta (informational)


class TestSuggestBody(BaseModel):
    target: str | None = None  # path prefix
    seed: int = 123


class SpeculateBody(BaseModel):
    description: str
    seed: int = 123


class ReviewBody(BaseModel):
    diff_summary: str
    links: list[str] = []


@router.post("/self/pr/docs")
def self_pr_docs(body: SelfDocsBody):
    # Offline: we do not open network PRs in tests; return a deterministic plan
    plan = {
        "status": "planned",
        "title": body.title,
        "summary": body.summary,
        "files": sorted(list(body.changes.keys())) if isinstance(body.changes, dict) else [],
        "status_context": "ai-csuite/self-docs",
    }
    return plan


@router.post("/self/tests/suggest")
def self_tests_suggest(body: TestSuggestBody):
    # Deterministic suggestion skeletons based on target path prefix
    target = (body.target or "apps/orchestrator/orchestrator").rstrip("/")
    suggestions = [
        {"path": f"apps/orchestrator/tests/test_synth_{i}.py", "target": target}
        for i in range(1, 4)
    ]
    return {"version": 1, "seed": int(body.seed), "suggestions": suggestions}


@router.post("/self/speculate")
def self_speculate(body: SpeculateBody, db: Session = Depends(get_db)):
    report = run_speculation(description=body.description, seed=body.seed)
    # persist DB + file artifact
    try:
        db.add(SpeculativeReport(id=str(uuid.uuid4()), report=report))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    out_path = os.path.join("apps", "orchestrator", "orchestrator", "self", "spec_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    return report


@router.post("/self/review")
def self_review(body: ReviewBody, db: Session = Depends(get_db)):
    review = run_agent_review(diff_summary=body.diff_summary, links=list(body.links or []))
    try:
        db.add(AgentReview(id=str(uuid.uuid4()), review=review, status="ai-csuite/self-review"))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return review


# ---------------- Phase 57–58: Self feature canary + eval gates ----------------


class SelfFeatureRegisterBody(BaseModel):
    feature_key: str
    title: str
    description: str
    seed: int = 123


class SelfFeatureCanaryBody(BaseModel):
    feature_key: str
    stage: int  # 5|25|50|100
    seed: int = 123
    # Optional overrides for deterministic tests
    eval_threshold: Optional[float] = None
    safety_text: Optional[str] = None
    latency_base_ms: Optional[int] = None
    latency_current_ms: Optional[int] = None
    latency_p95_delta_max_ms: Optional[int] = None


class SelfEvalGateBody(BaseModel):
    threshold: Optional[float] = None
    run_id: Optional[str] = None


def _self_policy_path() -> str:
    here = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(here, "self", "policy.json")


def _self_dir() -> str:
    return os.path.join("apps", "orchestrator", "orchestrator", "self")


def _read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json_sorted(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n"
    cur = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if content != cur:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def _load_self_policy() -> Dict[str, Any]:
    data = _read_json(_self_policy_path())
    if not isinstance(data, dict):
        data = {}
    # Defaults
    data.setdefault("eval_threshold", float(os.getenv("SELF_EVAL_THRESHOLD", "0.9")))
    data.setdefault("latency_p95_delta_max_ms", int(os.getenv("SELF_LATENCY_P95_DELTA_MAX_MS", "50")))
    data.setdefault("stages", [5, 25, 50, 100])
    return data


def _det_latency(seed: int, stage: int) -> int:
    rnd = random.Random(int(seed))
    base = 90 + int(rnd.random() * 20)  # 90..109ms baseline
    # Inflate with stage proportion deterministically
    inc = int((stage / 100.0) * (10 + int(rnd.random() * 20)))  # up to ~30ms
    return base + inc


@router.post("/self/feature/register")
def self_feature_register(body: SelfFeatureRegisterBody, db: Session = Depends(get_db)):
    # Persist manifest under self/
    manifest = {
        "feature_key": body.feature_key,
        "title": body.title,
        "description": body.description,
        "seed": int(body.seed),
        "status": "planned",
    }
    out_path = os.path.join(_self_dir(), f"feature_{body.feature_key}.json")
    _write_json_sorted(out_path, manifest)
    # Tie to feature flag via experiments provider
    try:
        experiments = registry().get("experiments")
        experiments.set_flag(body.feature_key, False)
    except Exception:
        pass
    try:
        audit_event(db, actor="api", event_type="self.feature.register", request_id=f"self:{body.feature_key}:register", details={"feature_key": body.feature_key, "title": body.title})
    except Exception:
        pass
    return {"status": "planned", "feature_key": body.feature_key, "flag_default": False}


@router.post("/self/feature/canary")
def self_feature_canary(body: SelfFeatureCanaryBody, db: Session = Depends(get_db)):
    policy = _load_self_policy()
    if body.stage not in {5, 25, 50, 100}:
        raise HTTPException(400, "invalid stage")
    # Apply ramp
    experiments = registry().get("experiments")
    try:
        experiments.ramp(body.feature_key, int(body.stage))
    except Exception:
        raise HTTPException(500, "ramp failed")

    # Run evals harness and compute metrics deterministically
    threshold = float(body.eval_threshold if body.eval_threshold is not None else policy.get("eval_threshold", 0.9))
    try:
        # Reuse evals_run logic (offline)
        _ = evals_run(EvalsRunBody(run_id=f"self:{body.feature_key}", bundle_id="default", threshold=threshold), db)
        rep = _read_json(os.path.join("eval", "report.json")) or {"summary": {"score": 0.0}}
        eval_score = float(rep.get("summary", {}).get("score", 0.0))
    except Exception:
        eval_score = 0.0

    # Safety check on provided text (optional)
    safety_status = "allowed"
    blocked_terms: list[str] = []
    if (body.safety_text or "").strip():
        res = safety_moderate(ModerateBody(text=body.safety_text or ""), db)  # type: ignore
        if isinstance(res, JSONResponse):
            # blocked
            try:
                payload = json.loads(res.body.decode("utf-8"))  # type: ignore
            except Exception:
                payload = {"status": "blocked", "blocked_terms": []}
            safety_status = str(payload.get("status") or "blocked")
            blocked_terms = list(payload.get("blocked_terms") or [])
        else:
            safety_status = str(res.get("status"))
            blocked_terms = list(res.get("blocked_terms") or [])

    # Latency p95 comparison (synthetic, deterministic)
    base_ms = int(body.latency_base_ms) if body.latency_base_ms is not None else _det_latency(body.seed, 0)
    cur_ms = int(body.latency_current_ms) if body.latency_current_ms is not None else _det_latency(body.seed, body.stage)
    delta_ms = max(0, cur_ms - base_ms)
    max_delta = int(body.latency_p95_delta_max_ms) if body.latency_p95_delta_max_ms is not None else int(policy.get("latency_p95_delta_max_ms", 50))

    anomalies = {
        "eval_below_threshold": eval_score < threshold,
        "safety_blocked": safety_status == "blocked",
        "latency_regression": delta_ms > max_delta,
    }
    has_anomaly = any(anomalies.values())

    prev_stage = {5: 0, 25: 5, 50: 25, 100: 50}.get(int(body.stage), 0)
    applied_stage = int(body.stage)
    rolled_back = False
    if has_anomaly:
        try:
            experiments.ramp(body.feature_key, int(prev_stage))
            applied_stage = int(prev_stage)
            rolled_back = True
        except Exception:
            pass
        try:
            audit_event(db, actor="api", event_type="self.feature.rollback", request_id=f"self:{body.feature_key}:rollback:{body.stage}", details={"feature_key": body.feature_key, "from": int(body.stage), "to": applied_stage, "anomalies": anomalies})
        except Exception:
            pass
    else:
        try:
            audit_event(db, actor="api", event_type="self.feature.ramp", request_id=f"self:{body.feature_key}:ramp:{body.stage}", details={"feature_key": body.feature_key, "to": applied_stage})
        except Exception:
            pass

    report = {
        "feature_key": body.feature_key,
        "requested_stage": int(body.stage),
        "applied_stage": applied_stage,
        "rolled_back": rolled_back,
        "policy": {"eval_threshold": threshold, "latency_p95_delta_max_ms": max_delta},
        "metrics": {
            "eval_score": eval_score,
            "safety_status": safety_status,
            "blocked_terms": sorted(blocked_terms),
            "latency_p95_base_ms": base_ms,
            "latency_p95_current_ms": cur_ms,
            "latency_p95_delta_ms": delta_ms,
        },
        "anomalies": anomalies,
    }
    _write_json_sorted(os.path.join(_self_dir(), "canary_report.json"), report)
    return report


@router.post("/self/eval/gate")
def self_eval_gate(body: SelfEvalGateBody, db: Session = Depends(get_db)):
    policy = _load_self_policy()
    threshold = float(body.threshold if body.threshold is not None else policy.get("eval_threshold", 0.9))
    # Run harness
    res = evals_run(EvalsRunBody(run_id=body.run_id or "self:eval-gate", bundle_id="default", threshold=threshold), db)
    report = dict(res.get("report") or {})
    score = float(((report.get("summary") or {}).get("score")) or 0.0)
    status = "pass" if score >= threshold else "fail"
    out = {"status": status, "score": score, "threshold": threshold}
    _write_json_sorted(os.path.join(_self_dir(), "eval_gate.json"), out)
    try:
        audit_event(db, actor="api", event_type="self.eval.gate", request_id=f"self:eval:gate", details=out)
    except Exception:
        pass
    if status != "pass":
        raise HTTPException(400, detail=out)
    return out


