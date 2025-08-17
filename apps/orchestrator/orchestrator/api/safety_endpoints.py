from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SafetyAudit
from ..security import apply_redaction


router = APIRouter()


def _blocked_terms_path() -> str:
    here = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(here, "safety", "policies", "blocked_terms.json")


def _load_blocked_terms() -> List[str]:
    path = _blocked_terms_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return list(data.get("blocked_terms", []))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return ["banned", "illegal"]


class ModerateBody(BaseModel):
    text: str
    channel: Optional[str] = None
    allowlist: Optional[List[str]] = None


@router.post("/safety/moderate")
def safety_moderate(body: ModerateBody, db: Session = Depends(get_db)):
    terms = _load_blocked_terms()
    allow = set([t.lower() for t in (body.allowlist or [])])
    lower = body.text.lower()
    hits = [t for t in terms if (t.lower() not in allow) and (t.lower() in lower)]
    status = "blocked" if hits else "allowed"
    red = apply_redaction(body.text, mode="strict")
    row = SafetyAudit(id=str(uuid.uuid4()), item_type="creative", status=status, findings={"blocked_terms": sorted(hits)}, redacted_text=red)
    db.add(row)
    db.commit()
    if status == "blocked":
        return JSONResponse(status_code=400, content={"status": status, "blocked_terms": sorted(hits)})
    return {"status": status, "blocked_terms": sorted(hits), "redacted_text": red}



