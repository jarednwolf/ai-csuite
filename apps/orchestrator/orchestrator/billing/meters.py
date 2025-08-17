from __future__ import annotations

import calendar
import datetime as dt
import uuid
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..models import BillingUsage


def _period(now: Optional[dt.datetime] = None) -> str:
    t = now or dt.datetime.utcnow()
    return f"{t.year:04d}-{t.month:02d}"


def _default_meters() -> Dict[str, int]:
    return {
        "tokens": 0,
        "runs": 0,
        "preview_minutes": 0,
        "storage_mb": 0,
        "api_calls": 0,
    }


def _get_or_create_row(db: Session, tenant_id: str, period: str) -> BillingUsage:
    row = (
        db.query(BillingUsage)
        .filter(BillingUsage.tenant_id == tenant_id, BillingUsage.period == period)
        .first()
    )
    if row:
        return row
    row = BillingUsage(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        period=period,
        meters=_default_meters(),
        plan="community",
    )
    db.add(row)
    db.commit()
    return row


def increment(db: Session, tenant_id: str, **deltas: int) -> Dict:
    per = _period()
    row = _get_or_create_row(db, tenant_id, per)
    meters = dict(row.meters or _default_meters())
    for k, v in deltas.items():
        meters[k] = int(meters.get(k, 0)) + int(v or 0)
    row.meters = meters
    db.commit()
    return {"tenant_id": tenant_id, "period": per, "meters": meters, "plan": row.plan}


def get_usage(db: Session, tenant_id: str, period: Optional[str] = None) -> Dict:
    per = period or _period()
    row = _get_or_create_row(db, tenant_id, per)
    # Return stable key ordering
    meters = _default_meters()
    meters.update(row.meters or {})
    return {"tenant_id": tenant_id, "period": per, "meters": meters, "plan": row.plan}


def set_plan(db: Session, tenant_id: str, plan: str) -> Dict:
    per = _period()
    row = _get_or_create_row(db, tenant_id, per)
    plan_lc = plan.lower().strip()
    if plan_lc not in {"community", "hosted", "enterprise"}:
        plan_lc = "community"
    row.plan = plan_lc
    db.commit()
    return {"tenant_id": tenant_id, "period": per, "plan": plan_lc}


def enforce_plan(db: Session, tenant_id: str) -> Dict:
    usage = get_usage(db, tenant_id)
    plan = usage["plan"]
    meters = usage["meters"]
    # Deterministic quotas
    quotas = {
        "community": {"tokens": 100000, "runs": 10, "preview_minutes": 60, "storage_mb": 128, "api_calls": 1000},
        "hosted": {"tokens": 500000, "runs": 100, "preview_minutes": 600, "storage_mb": 1024, "api_calls": 10000},
        "enterprise": {"tokens": 1000000, "runs": 1000, "preview_minutes": 6000, "storage_mb": 10240, "api_calls": 100000},
    }[plan]
    overages = {}
    blocked = False
    for key, limit in quotas.items():
        val = int(meters.get(key, 0))
        if val > limit:
            overages[key] = {"used": val, "limit": limit}
            # For community plan, block; for hosted, queue; enterprise never blocks
            if plan == "community":
                blocked = True
    action = "ok"
    if overages:
        if plan == "community":
            action = "blocked"
        elif plan == "hosted":
            action = "queued"
        else:
            action = "ok"
    return {"plan": plan, "overages": overages, "action": action, "blocked": blocked}


