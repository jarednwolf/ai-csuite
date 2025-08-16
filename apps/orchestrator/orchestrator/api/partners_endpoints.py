from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import audit_event, mask_dict
from ..integrations import partners as svc


router = APIRouter(prefix="/integrations/partners", tags=["partners"])


@router.get("")
def list_partners():
    items = svc.list_partners()
    # Deterministic sort by partner_id already applied in service
    return items


class CallBody(BaseModel):
    op: str
    payload: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


@router.post("/{partner_id}/call")
def call_partner(partner_id: str, body: CallBody, db: Session = Depends(get_db)):
    try:
        ok, resp = svc.call_partner(partner_id, op=body.op, payload=body.payload, idempotency_key=body.idempotency_key)
    except KeyError:
        raise HTTPException(404, "partner not found")
    # Minimal audit with redaction
    try:
        audit_event(
            db,
            actor="api",
            event_type="partners.call",
            request_id=f"{partner_id}:call:{body.op}:{body.idempotency_key or ''}",
            details={
                "partner_id": partner_id,
                "op": body.op,
                "payload": mask_dict(body.payload or {}, mode="strict"),
                "result": mask_dict(resp, mode="strict"),
            },
        )
    except Exception:
        pass
    if not ok:
        return JSONResponse(status_code=400, content=resp)
    return resp


@router.get("/{partner_id}/policy")
def get_policy(partner_id: str):
    try:
        return svc.policy_for(partner_id)
    except KeyError:
        raise HTTPException(404, "partner not found")


class PolicyPatch(BaseModel):
    rate_limit: Optional[int] = None
    retry_max: Optional[int] = None
    backoff_ms: Optional[int] = None
    circuit_threshold: Optional[int] = None
    window_tokens: Optional[int] = None


@router.patch("/{partner_id}/policy")
def patch_policy(partner_id: str, patch: PolicyPatch, db: Session = Depends(get_db)):
    try:
        res = svc.patch_policy(partner_id, {k: v for k, v in patch.dict().items() if v is not None})
    except KeyError:
        raise HTTPException(404, "partner not found")
    # Audit
    try:
        audit_event(db, actor="api", event_type="partners.policy", request_id=f"{partner_id}:policy", details={"partner_id": partner_id, "policy": res})
    except Exception:
        pass
    return res


@router.get("/{partner_id}/stats")
def get_stats(partner_id: str):
    try:
        return svc.stats_for(partner_id)
    except KeyError:
        raise HTTPException(404, "partner not found")


@router.post("/{partner_id}/reset")
def reset_stats(partner_id: str, db: Session = Depends(get_db)):
    try:
        res = svc.reset_partner(partner_id)
    except KeyError:
        raise HTTPException(404, "partner not found")
    try:
        audit_event(db, actor="api", event_type="partners.reset", request_id=f"{partner_id}:reset", details={"partner_id": partner_id})
    except Exception:
        pass
    return res


@router.post("/tick")
def tick():
    return svc.tick_all()



