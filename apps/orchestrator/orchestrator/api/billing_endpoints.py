from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..billing import meters as bm
from ..billing.invoices import generate_mock_invoice
from ..security import audit_event
from ..rbac import scopes_for_role, require_scope


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
def billing_usage(tenant_id: str = Query(...), period: Optional[str] = Query(default=None), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:billing"):
        raise HTTPException(403, "forbidden")
    res = bm.get_usage(db, tenant_id, period)
    try:
        audit_event(db, actor="api", event_type="billing.usage", request_id=f"usage:{tenant_id}:{res['period']}", details=res)
    except Exception:
        pass
    return res


class PlanSetBody(BaseModel):
    tenant_id: str
    plan: str


@router.post("/plan/set")
def billing_set_plan(body: PlanSetBody, db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:billing"):
        raise HTTPException(403, "forbidden")
    res = bm.set_plan(db, body.tenant_id, body.plan)
    try:
        audit_event(db, actor="api", event_type="billing.plan.set", request_id=f"plan:{body.tenant_id}", details=res)
    except Exception:
        pass
    return res


class InvoiceBody(BaseModel):
    tenant_id: str
    period: Optional[str] = None


@router.post("/invoice/mock")
def billing_invoice_mock(body: InvoiceBody, db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:billing"):
        raise HTTPException(403, "forbidden")
    usage = bm.get_usage(db, body.tenant_id, body.period)
    res = generate_mock_invoice(db, body.tenant_id, usage["period"], usage["meters"], usage["plan"])
    try:
        audit_event(db, actor="api", event_type="billing.invoice.mock", request_id=f"invoice:{body.tenant_id}:{usage['period']}", details={"amount_cents": res["amount_cents"]})
    except Exception:
        pass
    return res


