from __future__ import annotations

from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.budget import BudgetService
from ..security import audit_event


router = APIRouter()


class RateModel(BaseModel):
    usd_per_1k_tokens: float = Field(default=0.01, ge=0)


class ComputeBody(BaseModel):
    warn_pct: Optional[float] = Field(default=None, ge=0, le=1)
    block_pct: Optional[float] = Field(default=None, ge=0, le=1)
    rate: Optional[RateModel] = None
    personas: Optional[List[str]] = None


@router.post("/integrations/budget/{run_id}/compute")
def budget_compute(run_id: str, body: ComputeBody, db: Session = Depends(get_db)):
    svc = BudgetService()
    try:
        res = svc.compute(
            db,
            run_id,
            warn_pct=body.warn_pct,
            block_pct=body.block_pct,
            rate_usd_per_1k=(body.rate.usd_per_1k_tokens if body.rate else None),
            personas=body.personas,
        )
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Audit (idempotent)
    try:
        audit_event(
            db,
            actor="api",
            event_type="budget.compute",
            run_id=run_id,
            project_id=None,
            request_id=f"{run_id}:budget:compute",
            details={
                "warn_pct": body.warn_pct,
                "block_pct": body.block_pct,
                "personas": body.personas,
                "result": res,
            },
        )
    except Exception:
        pass
    return res


@router.get("/integrations/budget/{run_id}")
def budget_get(run_id: str, db: Session = Depends(get_db)):
    svc = BudgetService()
    try:
        res = svc.get(db, run_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        audit_event(
            db,
            actor="api",
            event_type="budget.get",
            run_id=run_id,
            project_id=None,
            request_id=f"{run_id}:budget:get",
            details={"result": res},
        )
    except Exception:
        pass
    return res


@router.post("/integrations/budget/{run_id}/reset")
def budget_reset(run_id: str, db: Session = Depends(get_db)):
    svc = BudgetService()
    res = svc.reset(db, run_id)
    try:
        audit_event(
            db,
            actor="api",
            event_type="budget.reset",
            run_id=run_id,
            project_id=None,
            request_id=f"{run_id}:budget:reset",
            details={"result": res},
        )
    except Exception:
        pass
    return res


