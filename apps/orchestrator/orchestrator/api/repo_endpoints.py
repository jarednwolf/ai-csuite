from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RepoMap as RepoMapDB, RepoHotspot as RepoHotspotDB
from ..repo.indexer import build_repo_map, compute_hotspots
from ..repo.ownership import compute_ownership


router = APIRouter(prefix="", tags=["repo"])


@router.get("/repo/map")
def repo_map(reindex: bool = Query(False), seed: int = Query(123), db: Session = Depends(get_db)):
    if not reindex:
        row = db.query(RepoMapDB).order_by(RepoMapDB.created_at.desc()).first()
        if row and isinstance(row.map, dict):
            return row.map
    # Build and persist
    m = build_repo_map(seed=seed)
    try:
        db.add(RepoMapDB(id=str(uuid.uuid4()), map=m))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return m


@router.get("/repo/ownership")
def repo_ownership(db: Session = Depends(get_db)):
    row = db.query(RepoMapDB).order_by(RepoMapDB.created_at.desc()).first()
    m = row.map if row and isinstance(row.map, dict) else build_repo_map()
    return compute_ownership(m)


@router.get("/repo/hotspots")
def repo_hotspots(recompute: bool = Query(False), db: Session = Depends(get_db)):
    if not recompute:
        row = db.query(RepoHotspotDB).order_by(RepoHotspotDB.created_at.desc()).first()
        if row and isinstance(row.hotspots, dict):
            return row.hotspots
    # Need a map
    map_row = db.query(RepoMapDB).order_by(RepoMapDB.created_at.desc()).first()
    m = map_row.map if map_row and isinstance(map_row.map, dict) else build_repo_map()
    hs = compute_hotspots(m)
    try:
        db.add(RepoHotspotDB(id=str(uuid.uuid4()), hotspots=hs))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return hs


