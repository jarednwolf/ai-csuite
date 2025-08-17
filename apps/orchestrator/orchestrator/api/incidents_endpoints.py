from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.incidents import IncidentService
from ..security import audit_event


router = APIRouter(prefix="/incidents", tags=["incidents"])


class RevertBody(BaseModel):
    run_id: str
    reason: str


class BisectBody(BaseModel):
    run_id: str
    start_sha: str
    end_sha: str


@router.post("/revert")
def incidents_revert(body: RevertBody, db: Session = Depends(get_db)):
    svc = IncidentService()
    try:
        res = svc.open_revert(db, run_id=body.run_id, reason=body.reason)
    except LookupError as e:
        raise HTTPException(404, str(e))
    try:
        audit_event(db, actor="api", event_type="incident.revert", run_id=body.run_id, request_id=f"{body.run_id}:incident:revert", details={"reason": body.reason, **res})
    except Exception:
        pass
    return res


@router.post("/bisect")
def incidents_bisect(body: BisectBody, db: Session = Depends(get_db)):
    svc = IncidentService()
    try:
        res = svc.open_bisect(db, run_id=body.run_id, start_sha=body.start_sha, end_sha=body.end_sha)
    except LookupError as e:
        raise HTTPException(404, str(e))
    try:
        audit_event(db, actor="api", event_type="incident.bisect", run_id=body.run_id, request_id=f"{body.run_id}:incident:bisect", details={"start": body.start_sha, "end": body.end_sha, **res})
    except Exception:
        pass
    return res


