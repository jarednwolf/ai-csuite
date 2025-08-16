from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import audit_event
from ..services.postmortem import PostmortemService


router = APIRouter(prefix="/postmortems", tags=["postmortems"])


@router.get("/{run_id}")
def get_postmortem(run_id: str):
    svc = PostmortemService()
    try:
        art = svc.get(run_id)
    except LookupError:
        raise HTTPException(404, "not found")
    return art


@router.post("/{run_id}/generate")
def generate_postmortem(run_id: str, db: Session = Depends(get_db)):
    svc = PostmortemService()
    try:
        res = svc.generate(db, run_id)
    except LookupError:
        raise HTTPException(404, "run not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        audit_event(db, actor="api", event_type="postmortem.generate", run_id=run_id, request_id=f"{run_id}:pm:gen", details={"metrics": res.get("metrics")})
    except Exception:
        pass
    return res


@router.post("/{run_id}/reset")
def reset_postmortem(run_id: str, db: Session = Depends(get_db)):
    svc = PostmortemService()
    res = svc.reset(run_id)
    try:
        audit_event(db, actor="api", event_type="postmortem.reset", run_id=run_id, request_id=f"{run_id}:pm:reset", details=res)
    except Exception:
        pass
    return res


@router.post("/{run_id}/ingest-kb")
def ingest_kb_postmortem(run_id: str, db: Session = Depends(get_db)):
    svc = PostmortemService()
    try:
        res = svc.ingest_kb(db, run_id)
    except LookupError:
        raise HTTPException(404, "not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        audit_event(db, actor="api", event_type="postmortem.ingest_kb", run_id=run_id, request_id=f"{run_id}:pm:kb", details=res)
    except Exception:
        pass
    return res


@router.get("/search")
def search_postmortems(q: Optional[str] = Query(default=None), tag: Optional[str] = Query(default=None)):
    svc = PostmortemService()
    return svc.search(q=q, tag=tag)


