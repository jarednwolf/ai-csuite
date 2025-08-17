from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..models import AttributionReport, ExperimentState, PlanningValueScore


@dataclass
class ROIInputs:
    tenant_id: str
    project_id: str
    idea_id: str
    attribution_id: Optional[str] = None
    experiment_id: Optional[str] = None
    cost_cents: Optional[int] = None


def _fetch_attribution_lift(db: Session, attribution_id: Optional[str]) -> float:
    row: Optional[AttributionReport] = None
    if attribution_id:
        row = db.get(AttributionReport, attribution_id)
    else:
        row = (
            db.query(AttributionReport)
            .order_by(AttributionReport.created_at.desc())
            .first()
        )
    if not row:
        return 0.0
    winners = list(row.report.get("winners", [])) if isinstance(row.report, dict) else []
    if not winners:
        return 0.0
    lifts = []
    for w in winners:
        try:
            lifts.append(float(w.get("lift", 0.0)))
        except Exception:
            continue
    if not lifts:
        return 0.0
    return sum(lifts) / float(len(lifts))


def _fetch_experiment_cr(db: Session, experiment_id: Optional[str]) -> float:
    if not experiment_id:
        # Best effort: latest state for any experiment
        row = (
            db.query(ExperimentState)
            .order_by(ExperimentState.created_at.desc())
            .first()
        )
    else:
        row = (
            db.query(ExperimentState)
            .filter(ExperimentState.experiment_id == str(experiment_id))
            .order_by(ExperimentState.created_at.desc())
            .first()
        )
    if not row:
        return 0.0
    # Deterministic synthetic report used by experiments endpoint
    arm = row.state.get("arm")
    if not arm:
        return 0.0
    # Use a stable CR proxy; align with experiments endpoint default
    # If state contains metrics, prefer them
    metrics = row.state.get("metrics") or {}
    cr = metrics.get("cr")
    if isinstance(cr, (int, float)):
        return float(cr)
    # Fallback constant consistent with experiments report stub
    return 0.02


def compute_value_score(db: Session, inputs: ROIInputs) -> Dict[str, Any]:
    """
    Deterministic Value Score in basis points (0..10000):
      score = round(10000 * clamp(0, 1, 0.5*lift + 0.4*cr + 0.1*eff))
    where
      lift = mean attribution winner.lift (0..1)
      cr = experiment conversion rate (0..1)
      eff = 1 - min(1, cost/$100)
    """
    lift = _fetch_attribution_lift(db, inputs.attribution_id)
    cr = _fetch_experiment_cr(db, inputs.experiment_id)
    # Cost efficiency: baseline $100 budget for normalization
    cost_cents = int(inputs.cost_cents or 0)
    eff = 1.0 - min(1.0, (cost_cents / 100.0) / 100.0)
    raw = (0.5 * lift) + (0.4 * cr) + (0.1 * eff)
    raw = max(0.0, min(1.0, raw))
    bps = int(round(raw * 10000.0))

    rationale = {
        "attribution": {"mean_lift": round(float(lift), 6), "source_id": inputs.attribution_id},
        "experiment": {"cr": round(float(cr), 6), "experiment_id": inputs.experiment_id},
        "cost_cents": cost_cents,
        "formula": "0.5*lift + 0.4*cr + 0.1*eff",
    }

    row = PlanningValueScore(
        id=str(uuid.uuid4()),
        tenant_id=str(inputs.tenant_id),
        project_id=str(inputs.project_id),
        idea_id=str(inputs.idea_id),
        score=bps,
        rationale=rationale,
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {
        "idea_id": inputs.idea_id,
        "score_bps": bps,
        "rationale": rationale,
    }


