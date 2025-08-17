from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ExperimentState, AdsCampaign, AudienceSyncJob, PlanningValueScore
from ..rbac import scopes_for_role, require_scope
from ..security import audit_event


router = APIRouter(prefix="/cockpit", tags=["cockpit"])


@router.get("/experiments")
def cockpit_experiments(tenant_id: Optional[str] = Query(default=None), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:cockpit"):
        raise HTTPException(403, "forbidden")
    q = db.query(ExperimentState)
    items = q.order_by(ExperimentState.created_at.desc()).limit(20).all()
    out = [
        {"experiment_id": r.experiment_id, "arm": r.state.get("arm"), "created_at": r.created_at.isoformat()}
        for r in items
    ]
    return {"items": out}


@router.get("/campaigns")
def cockpit_campaigns(db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:cockpit"):
        raise HTTPException(403, "forbidden")
    items = db.query(AdsCampaign).order_by(AdsCampaign.created_at.desc()).limit(20).all()
    out = [
        {"campaign_id": r.campaign_id, "status": r.status, "created_at": r.created_at.isoformat()}
        for r in items
    ]
    return {"items": out}


@router.get("/audiences")
def cockpit_audiences(db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:cockpit"):
        raise HTTPException(403, "forbidden")
    items = db.query(AudienceSyncJob).order_by(AudienceSyncJob.created_at.desc()).limit(20).all()
    out = [
        {"job_id": r.id, "status": r.status, "size": (r.audience or {}).get("size", 0), "created_at": r.created_at.isoformat()}
        for r in items
    ]
    return {"items": out}


@router.get("/roi")
def cockpit_roi(tenant_id: str = Query(...), project_id: str = Query(...), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:cockpit"):
        raise HTTPException(403, "forbidden")
    rows = (
        db.query(PlanningValueScore)
        .filter(PlanningValueScore.tenant_id == tenant_id, PlanningValueScore.project_id == project_id)
        .order_by(PlanningValueScore.score.desc(), PlanningValueScore.created_at.asc())
        .limit(5)
        .all()
    )
    return {"top_5": [{"idea_id": r.idea_id, "score_bps": int(r.score)} for r in rows]}


# Control actions (networkless)
@router.post("/actions/kill-switch")
def cockpit_kill_switch(resource: str = Query(...), enable: bool = Query(True), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:cockpit"):
        raise HTTPException(403, "forbidden")
    try:
        audit_event(db, actor="api", event_type="cockpit.kill_switch", request_id=f"kill:{resource}", details={"resource": resource, "enable": enable})
    except Exception:
        pass
    return {"resource": resource, "enabled": bool(enable)}


@router.post("/actions/ramp")
def cockpit_ramp(feature: str = Query(...), percent: int = Query(..., ge=0, le=100), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:cockpit"):
        raise HTTPException(403, "forbidden")
    try:
        audit_event(db, actor="api", event_type="cockpit.ramp", request_id=f"ramp:{feature}:{percent}", details={"feature": feature, "percent": percent})
    except Exception:
        pass
    return {"feature": feature, "percent": int(percent)}


@router.post("/actions/approve-spend")
def cockpit_approve_spend(campaign_id: str = Query(...), amount_cents: int = Query(..., ge=0), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:cockpit"):
        raise HTTPException(403, "forbidden")
    try:
        audit_event(db, actor="api", event_type="cockpit.approve_spend", request_id=f"spend:{campaign_id}", details={"campaign_id": campaign_id, "amount_cents": amount_cents})
    except Exception:
        pass
    return {"campaign_id": campaign_id, "approved_cents": int(amount_cents)}


