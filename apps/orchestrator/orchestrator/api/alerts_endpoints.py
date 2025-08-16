from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.alerts import AlertsService


router = APIRouter(prefix="/integrations/alerts", tags=["alerts"])


class ComputeBody(BaseModel):
    window: Optional[int] = None
    stuck_ms: Optional[int] = None
    burn_pct: Optional[float] = None
    retry_exhaust_max: Optional[int] = None


@router.post("/{run_id}/compute")
def compute_alerts(run_id: str, body: ComputeBody, db: Session = Depends(get_db)):
    svc = AlertsService()
    try:
        res = svc.compute(db, run_id, overrides={
            k: v for k, v in {
                "window": body.window,
                "stuck_ms": body.stuck_ms,
                "burn_pct": body.burn_pct,
                "retry_exhaust_max": body.retry_exhaust_max,
            }.items() if v is not None
        })
    except LookupError:
        raise HTTPException(404, "run not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return res


@router.get("/{run_id}")
def get_alerts(run_id: str, db: Session = Depends(get_db)):
    svc = AlertsService()
    try:
        res = svc.get_snapshot(db, run_id)
    except LookupError:
        raise HTTPException(404, "run not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return res


@router.post("/{run_id}/reset")
def reset_alerts(run_id: str, db: Session = Depends(get_db)):
    svc = AlertsService()
    try:
        res = svc.reset(db, run_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return res


