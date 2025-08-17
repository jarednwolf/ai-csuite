from __future__ import annotations

import json, os, uuid, random, time
from typing import Any, Dict, Mapping, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ExperimentState
from ..providers.registry import registry


router = APIRouter(prefix="", tags=["experiments"])


def _policy_path() -> str:
    here = os.path.dirname(os.path.dirname(__file__))
    p = os.path.join(here, "experiments", "policy.json")
    if not os.path.exists(p):
        alt = os.path.join(os.getcwd(), "apps", "orchestrator", "orchestrator", "experiments", "policy.json")
        if os.path.exists(alt):
            p = alt
    return p


def _load_policy() -> Dict[str, Any]:
    p = _policy_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stopping_rules": {"max_days": 14}, "mde": {"min_effect": 0.05}}


class ExperimentStartBody(BaseModel):
    experiment_id: str
    plan: Mapping[str, Any]
    seed: Optional[int] = 123


@router.post("/experiments/start")
def experiments_start(body: ExperimentStartBody, db: Session = Depends(get_db)):
    # deterministic seeded RNG for bandits
    rnd = random.Random(body.seed or 123)
    provider = registry().get("experiments")
    plan = dict(body.plan)
    # flags and simple AB from plan
    flags = dict(plan.get("flags", {}))
    for k, v in sorted(flags.items(), key=lambda kv: str(kv[0])):
        provider.set_flag(k, v)
    variant_weights = plan.get("variants", {"A": 0.5, "B": 0.5})
    variants_sorted = sorted(variant_weights.items(), key=lambda kv: str(kv[0]))
    # simple MAB: pick argmax of prior weights with slight noise
    choices = [(name, weight + 0.0001 * rnd.random()) for name, weight in variants_sorted]
    choices.sort(key=lambda x: (-x[1], str(x[0])))
    arm = choices[0][0]
    # contextual hook (deterministic mock)
    context = plan.get("context", {})
    if context:
        # choose arm whose name has min lexical distance to a context key for determinism
        key = sorted(context.keys())[0]
        arm = min([a for a, _ in variants_sorted], key=lambda a: abs(len(a) - len(key)))
    state = {"arm": arm, "flags": flags, "policy": _load_policy(), "seed": int(body.seed or 123)}
    row = ExperimentState(id=str(uuid.uuid4()), experiment_id=str(body.experiment_id), plan=plan, state=state)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "db error")
    return {"experiment_id": body.experiment_id, "arm": arm, "state_id": row.id}


@router.get("/experiments/{experiment_id}/report")
def experiments_report(experiment_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(ExperimentState)
        .filter(ExperimentState.experiment_id == str(experiment_id))
        .order_by(ExperimentState.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(404, "experiment not found")
    # Synthesize deterministic report
    arm = row.state.get("arm")
    report = {"id": experiment_id, "winner": arm, "arms": {arm: {"ctr": 0.1, "cr": 0.02}}, "policy": row.state.get("policy", {})}
    return report


class FlagRampBody(BaseModel):
    key: str
    stage: int


@router.post("/flags/ramp")
def flags_ramp(body: FlagRampBody):
    if body.stage not in {5, 25, 50, 100}:
        raise HTTPException(400, "invalid stage")
    provider = registry().get("experiments")
    res = provider.ramp(body.key, int(body.stage))
    return {"ok": True, "result": dict(res)}


