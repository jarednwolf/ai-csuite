from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..planning.roi import compute_value_score, ROIInputs
from ..models import PlanningValueScore
from ..security import audit_event
from ..rbac import scopes_for_role, require_scope


router = APIRouter(prefix="", tags=["planning"])


class ROIScoreBody(BaseModel):
    tenant_id: str
    project_id: str
    idea_id: str
    attribution_id: Optional[str] = None
    experiment_id: Optional[str] = None
    cost_cents: Optional[int] = 0


@router.post("/planning/roi/score")
def planning_roi_score(body: ROIScoreBody, db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:planning"):
        raise HTTPException(403, "forbidden")
    res = compute_value_score(
        db,
        ROIInputs(
            tenant_id=body.tenant_id,
            project_id=body.project_id,
            idea_id=body.idea_id,
            attribution_id=body.attribution_id,
            experiment_id=body.experiment_id,
            cost_cents=body.cost_cents or 0,
        ),
    )
    try:
        audit_event(db, actor="api", event_type="planning.roi.score", request_id=f"roi:{body.idea_id}", details=res)
    except Exception:
        pass
    return res


class SuggestBody(BaseModel):
    tenant_id: str
    project_id: str
    k: int = 5


@router.post("/roadmap/suggest")
def roadmap_suggest(body: SuggestBody, db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:planning"):
        raise HTTPException(403, "forbidden")
    q = (
        db.query(PlanningValueScore)
        .filter(PlanningValueScore.tenant_id == body.tenant_id, PlanningValueScore.project_id == body.project_id)
        .order_by(PlanningValueScore.score.desc(), PlanningValueScore.created_at.asc())
        .limit(int(max(1, min(50, body.k or 5))))
        .all()
    )
    out = [
        {
            "idea_id": r.idea_id,
            "score_bps": int(r.score),
            "rationale": dict(r.rationale or {}),
        }
        for r in q
    ]
    try:
        audit_event(db, actor="api", event_type="roadmap.suggest", request_id=f"suggest:{body.project_id}", details={"count": len(out)})
    except Exception:
        pass
    # Top 5 ROI opportunities for Cockpit card
    return {"top_opportunities": out}


