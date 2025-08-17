from __future__ import annotations

import time, uuid
from typing import Any, Mapping, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AdsCampaign
from ..providers.registry import registry


router = APIRouter(prefix="/ads", tags=["ads"])


class CampaignBody(BaseModel):
    plan: Mapping[str, Any]


def _budget_guard(plan: Mapping[str, Any]) -> Optional[str]:
    budget_cents = int(plan.get("budget_cents", 0) or 0)
    spent_cents = int(plan.get("spent_cents", 0) or 0)
    if budget_cents <= 0:
        return "missing budget"
    pct = spent_cents / float(budget_cents)
    if pct >= 1.0:
        return "budget exceeded"
    # safety stops (CPA/ROAS) — deterministic stubs
    cpa = plan.get("cpa", 0)
    roas = plan.get("roas", 1.0)
    if isinstance(cpa, (int, float)) and cpa and cpa > plan.get("cpa_limit", 999999):
        return "cpa too high"
    if isinstance(roas, (int, float)) and roas and roas < plan.get("roas_floor", 0.1):
        return "roas too low"
    return None


@router.post("/campaigns")
def create_campaign(body: CampaignBody, db: Session = Depends(get_db)):
    # treat AI campaign kinds as first-class: kind in {pmax, adv_plus, accelerate}
    kind = str(body.plan.get("kind", "")).lower()
    if kind not in {"pmax", "adv_plus", "accelerate", "standard", ""}:
        raise HTTPException(400, "unsupported campaign kind")
    guard = _budget_guard(body.plan)
    if guard:
        raise HTTPException(400, guard)
    provider = registry().get("ads")
    start = time.time()
    res = provider.create_campaign(dict(body.plan))
    row = AdsCampaign(id=str(uuid.uuid4()), campaign_id=str(res.get("id")), plan=dict(body.plan), status=str(res.get("status", "active")))
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    latency_ms = int((time.time() - start) * 1000)
    return {"id": str(res.get("id")), "status": str(res.get("status", "active")), "metrics": {"latency_ms": latency_ms}}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: str, db: Session = Depends(get_db)):
    provider = registry().get("ads")
    provider.pause(campaign_id)
    row = AdsCampaign(id=str(uuid.uuid4()), campaign_id=campaign_id, plan={}, status="paused")
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {"id": campaign_id, "status": "paused"}


@router.get("/{campaign_id}/report")
def campaign_report(campaign_id: str):
    provider = registry().get("ads")
    rows = provider.report({"campaign_id": campaign_id})
    # Govern budget usage
    spend = sum(int(r.get("spend_cents", 0) or 0) for r in rows)
    return {"campaign_id": campaign_id, "spend_cents": spend, "rows": list(rows)}


