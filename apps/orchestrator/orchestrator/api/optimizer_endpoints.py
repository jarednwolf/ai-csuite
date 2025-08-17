from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.optimizer import OptimizerService
from ..security import audit_event


router = APIRouter(prefix="/self", tags=["self-optimizer"])


class OptimizeBody(BaseModel):
    run_id: str
    seed: int = 123


@router.post("/optimize")
def optimize(body: OptimizeBody, db: Session = Depends(get_db)):
    svc = OptimizerService()
    try:
        rep = svc.analyze(db, body.run_id, seed=int(body.seed))
    except LookupError as e:
        raise HTTPException(404, str(e))
    try:
        audit_event(db, actor="api", event_type="self.optimize", run_id=body.run_id, request_id=f"{body.run_id}:self:optimize", details={"seed": int(body.seed), "artifact": rep.get("artifact_path")})
    except Exception:
        pass
    return rep


