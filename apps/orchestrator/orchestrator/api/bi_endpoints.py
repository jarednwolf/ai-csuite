from __future__ import annotations

import json, os, uuid
from typing import Any, Dict, Mapping, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BIInsight


router = APIRouter(prefix="", tags=["bi"])  # no nested prefix for explicit endpoints


def _catalog_path() -> str:
    here = os.path.dirname(os.path.dirname(__file__))
    p = os.path.join(here, "metrics", "metric_catalog.json")
    if not os.path.exists(p):
        alt = os.path.join(os.getcwd(), "apps", "orchestrator", "orchestrator", "metrics", "metric_catalog.json")
        if os.path.exists(alt):
            p = alt
    return p


def _load_catalog() -> Dict[str, Any]:
    p = _catalog_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"kpis": {"activation": {}, "retention_7d": {}, "cac": {}, "ltv": {}, "roas": {}}}


@router.get("/metrics/catalog")
def metrics_catalog():
    cat = _load_catalog()
    return cat


class InsightsRunBody(BaseModel):
    run_id: Optional[str] = None
    query: Optional[str] = None
    params: Optional[Mapping[str, Any]] = None


@router.post("/bi/insights/run")
def bi_insights_run(body: InsightsRunBody, db: Session = Depends(get_db)):
    catalog = _load_catalog()
    # Deterministic mock insights grounded on catalog keys
    kpis = sorted(list(catalog.get("kpis", {}).keys()))
    insights = {"top_kpis": kpis[:3], "notes": "Deterministic mock insights grounded on catalog."}
    row = BIInsight(id=str(uuid.uuid4()), run_id=body.run_id, insights=insights)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {"insights_id": row.id, "insights": insights}


class SuggestionsFileBody(BaseModel):
    run_id: Optional[str] = None
    context: Optional[Mapping[str, Any]] = None


@router.post("/bi/suggestions/file")
def bi_suggestions_file(body: SuggestionsFileBody, db: Session = Depends(get_db)):
    catalog = _load_catalog()
    suggestions = {
        "roadmap": [
            {"id": "kpi-1", "title": "Improve activation funnel", "kpi": "activation"},
            {"id": "kpi-2", "title": "Boost 7-day retention", "kpi": "retention_7d"},
        ]
    }
    row = BIInsight(id=str(uuid.uuid4()), run_id=body.run_id, insights={}, suggestions=suggestions)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {"filed": True, "suggestions_id": row.id, "count": len(suggestions.get("roadmap", []))}


