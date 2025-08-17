from __future__ import annotations

import time, uuid
from typing import Any, Mapping, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import LifecycleSend
from ..providers.registry import registry


router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


class SendBody(BaseModel):
    channel: str
    to: str
    body: Mapping[str, Any]
    consent: Optional[Mapping[str, Any]] = None


class SequenceBody(BaseModel):
    items: List[SendBody]
    rate_limit_per_min: int = 120


class PreviewBody(BaseModel):
    channel: str
    body: Mapping[str, Any]


_BLOCKED_TERMS = {"guaranteed", "risk-free"}


def _pre_send_check(body: Mapping[str, Any]) -> Optional[str]:
    text = str(body)
    for t in sorted(_BLOCKED_TERMS):
        if t in text:
            return f"blocked term: {t}"
    return None


@router.post("/send")
def lifecycle_send(body: SendBody, db: Session = Depends(get_db)):
    # consent check
    consent = body.consent or {}
    if str(body.channel).lower() == "email" and not consent.get("email_opt_in", True):
        row = LifecycleSend(id=str(uuid.uuid4()), channel=body.channel, recipient=body.to, message=dict(body.body), status="blocked")
        db.add(row)
        db.commit()
        raise HTTPException(400, "consent blocked")
    err = _pre_send_check(body.body)
    if err:
        row = LifecycleSend(id=str(uuid.uuid4()), channel=body.channel, recipient=body.to, message=dict(body.body), status="blocked")
        db.add(row)
        db.commit()
        raise HTTPException(400, err)
    provider = registry().get("lifecycle")
    res = provider.send({"to": body.to, "channel": body.channel, "body": dict(body.body)})
    row = LifecycleSend(id=str(uuid.uuid4()), channel=body.channel, recipient=body.to, message=dict(body.body), status="sent")
    db.add(row)
    db.commit()
    return {"id": res.get("id"), "status": "sent"}


@router.post("/sequence")
def lifecycle_sequence(body: SequenceBody):
    # deterministic limit: do not actually delay
    provider = registry().get("lifecycle")
    scheduled = 0
    for it in list(body.items or []):
        if _pre_send_check(it.body):
            continue
        scheduled += 1
    out = provider.schedule([{"to": it.to, "channel": it.channel} for it in body.items], {"rate_limit_per_min": body.rate_limit_per_min})
    return {"scheduled": min(scheduled, len(body.items or [])), "provider": out}


@router.post("/preview")
def lifecycle_preview(body: PreviewBody):
    # return a canonical render stub for deterministic testing
    text = str(body.body)
    return {"channel": body.channel, "render": {"text": text[:120], "length": len(text)}}


