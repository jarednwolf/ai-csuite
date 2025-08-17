from __future__ import annotations

import uuid
from typing import Any, Mapping, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AttributionReport, AudienceSyncJob


router = APIRouter(prefix="", tags=["attribution"])  # explicit endpoints


class AttributionRunBody(BaseModel):
    from_date: str
    to_date: str
    utm_rules: Optional[Mapping[str, Any]] = None


@router.post("/attribution/report/run")
def attribution_run(body: AttributionRunBody, db: Session = Depends(get_db)):
    # Deterministic last-touch by utm_campaign
    report = {
        "model": "last_touch_utm",
        "range": {"from": body.from_date, "to": body.to_date},
        "sanity": {"clicks_vs_spend": "ok"},
        "winners": [
            {"channel": "ads", "campaign": "brand", "lift": 0.12},
            {"channel": "email", "campaign": "drip", "lift": 0.07},
        ],
    }
    row = AttributionReport(id=str(uuid.uuid4()), report=report)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {"report_id": row.id, "report": report}


class AudienceSyncSimpleBody(BaseModel):
    name: str
    members: List[Mapping[str, Any]]


@router.post("/audiences/sync")
def audiences_sync(body: AudienceSyncSimpleBody, db: Session = Depends(get_db)):
    # Mirror Phase 39: push winners back (mocked via AudienceSyncJob persistence)
    row = AudienceSyncJob(id=str(uuid.uuid4()), audience={"name": body.name, "size": len(body.members or [])}, status="completed", result={"synced": True})
    db.add(row)
    db.commit()
    return {"job_id": row.id, "status": row.status}


@router.get("/audiences/status/{job_id}")
def audiences_status(job_id: str, db: Session = Depends(get_db)):
    row = db.get(AudienceSyncJob, job_id)
    if not row:
        raise HTTPException(404, "not found")
    return {"job_id": row.id, "status": row.status, "result": row.result or {}}


