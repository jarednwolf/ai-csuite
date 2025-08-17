from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Sequence

from ..providers.registry import registry
from ..providers.shadow import ShadowManager
from ..db import get_db
from sqlalchemy.orm import Session
import uuid
from ..models import ProviderConformanceReport, ProviderShadowDiff
from ..services.vendor_swap import VendorSwapService


router = APIRouter(prefix="/providers", tags=["providers"])


class ConformanceBody(BaseModel):
    capabilities: Optional[List[str]] = None
    adapters: Optional[List[str]] = None


@router.get("")
def list_providers():
    reg = registry()
    return reg.list_active()


@router.post("/reload")
def reload_providers():
    reg = registry()
    return reg.reload()


@router.post("/conformance/run")
def conformance_run(body: ConformanceBody, db: Session = Depends(get_db)):
    reg = registry()
    res = reg.run_conformance(body.capabilities, body.adapters)
    # Persist per-adapter reports deterministically
    try:
        for r in res.get("reports", []):
            row = ProviderConformanceReport(
                id=str(uuid.uuid4()),
                capability=str(r.get("capability")),
                adapter=str(r.get("adapter")),
                report=dict(r),
            )
            db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    # If an ads shadow is active, perform one deterministic compare to accumulate diff
    try:
        caps = body.capabilities or [r.get("capability") for r in res.get("reports", [])]
        if "ads" in set(caps or []):
            cmp_res = ShadowManager().dual_write_compare("ads", {"budget_cents": 1000, "geo": "US"})
            if cmp_res.get("shadow_id"):
                row = ProviderShadowDiff(
                    id=str(uuid.uuid4()),
                    shadow_id=str(cmp_res.get("shadow_id")),
                    capability="ads",
                    candidate=str(cmp_res.get("candidate")),
                    diff={"mismatches": int(cmp_res.get("mismatches", 0))},
                )
                db.add(row)
                db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return res


# ---- Phase 61 helper: deterministic shadow→ramp flow facade ----
class StartShadowBody(BaseModel):
    capability: str
    candidate: str


@router.post("/shadow/start/simple")
def shadow_start_simple(body: StartShadowBody):
    svc = VendorSwapService()
    return svc.start_shadow(body.capability, body.candidate)


class CompareBody(BaseModel):
    capability: str


@router.post("/shadow/compare-once")
def shadow_compare_once(body: CompareBody):
    svc = VendorSwapService()
    return svc.run_compare_once(body.capability)



class ShadowStartBody(BaseModel):
    capability: str
    candidate: str
    duration_sec: int = 120


@router.post("/shadow/start")
def shadow_start(body: ShadowStartBody):
    mgr = ShadowManager()
    return mgr.start(body.capability, body.candidate, body.duration_sec)


class ShadowStopBody(BaseModel):
    shadow_id: str


@router.post("/shadow/stop")
def shadow_stop(body: ShadowStopBody):
    mgr = ShadowManager()
    return mgr.stop(body.shadow_id)


class RampBody(BaseModel):
    capability: str
    candidate: str


@router.post("/ramp/{stage}")
def ramp(stage: int, body: RampBody):
    if stage not in {5, 25, 50, 100}:
        raise HTTPException(400, "invalid stage")
    mgr = ShadowManager()
    return mgr.ramp(body.capability, body.candidate, stage)


