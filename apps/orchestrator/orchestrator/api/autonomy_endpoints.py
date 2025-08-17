from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AutonomySetting


router = APIRouter()


class SetLevelBody(BaseModel):
    channel: str
    campaign_id: Optional[str] = None
    level: str


@router.post("/autonomy/level/set")
def set_autonomy_level(body: SetLevelBody, db: Session = Depends(get_db)):
    if body.level not in {"manual", "limited", "full"}:
        raise HTTPException(400, "invalid level")
    row = AutonomySetting(id=str(uuid.uuid4()), channel=body.channel, campaign_id=body.campaign_id, level=body.level)
    db.add(row)
    db.commit()
    return {"status": "ok", "channel": body.channel, "level": body.level}



