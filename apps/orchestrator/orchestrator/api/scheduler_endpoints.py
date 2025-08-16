from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from ..db import get_db
from ..services.scheduler import enqueue as sched_enqueue
from ..services.scheduler import snapshot as sched_snapshot
from ..services.scheduler import step as sched_step
from ..services.scheduler import get_policy as sched_get_policy
from ..services.scheduler import patch_policy as sched_patch_policy
from ..services.scheduler import get_stats as sched_get_stats


router = APIRouter()


class EnqueueBody(BaseModel):
    run_id: str = Field(...)
    priority: Optional[int] = Field(default=None, ge=-1000, le=1000)


@router.post("/scheduler/enqueue")
def scheduler_enqueue(body: EnqueueBody, db: Session = Depends(get_db)):
    res = sched_enqueue(db, body.run_id, priority=body.priority)
    if "error" in res:
        # Backpressure or not found
        raise HTTPException(400, res["error"])  # type: ignore[index]
    return res


@router.get("/scheduler/queue")
def scheduler_queue(db: Session = Depends(get_db)):
    return sched_snapshot(db)


@router.post("/scheduler/step")
def scheduler_step(db: Session = Depends(get_db)):
    return sched_step(db)


@router.get("/scheduler/policy")
def scheduler_policy_get():
    return sched_get_policy()


class PolicyPatch(BaseModel):
    enabled: Optional[bool] = None
    global_concurrency: Optional[int] = Field(default=None, ge=0, le=1000)
    tenant_max_active: Optional[int] = Field(default=None, ge=0, le=1000)
    queue_max: Optional[int] = Field(default=None, ge=1, le=100000)


@router.patch("/scheduler/policy")
def scheduler_policy_patch(body: PolicyPatch, db: Session = Depends(get_db)):
    return sched_patch_policy(db, {k: v for k, v in body.dict().items() if v is not None})


@router.get("/scheduler/stats")
def scheduler_stats():
    return sched_get_stats()


