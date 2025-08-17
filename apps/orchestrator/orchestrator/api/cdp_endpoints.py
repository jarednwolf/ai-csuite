from __future__ import annotations

import json, os, uuid, time
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CDPEvent, AudienceSyncJob
from ..providers.registry import registry


router = APIRouter(prefix="/cdp", tags=["cdp"])


class EventIngestBody(BaseModel):
    # Generic envelope to keep schema flexible; we validate internally
    events: List[Mapping[str, Any]]
    run_id: Optional[str] = None
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None


class AudienceSyncBody(BaseModel):
    name: str
    members: List[Mapping[str, Any]]
    meta: Optional[Mapping[str, Any]] = None


def _events_schema_path() -> str:
    here = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(here, "artifacts", "schemas", "events.schema.json")
    # Fallback: try repository root relative if running tests from root
    if not os.path.exists(path):
        alt = os.path.join(os.getcwd(), "apps", "orchestrator", "orchestrator", "artifacts", "schemas", "events.schema.json")
        if os.path.exists(alt):
            path = alt
    return path


_EVENT_SCHEMA: Optional[Dict[str, Any]] = None


def _load_event_schema() -> Dict[str, Any]:
    global _EVENT_SCHEMA
    if _EVENT_SCHEMA is None:
        p = _events_schema_path()
        try:
            with open(p, "r", encoding="utf-8") as f:
                _EVENT_SCHEMA = json.load(f)
        except Exception:
            _EVENT_SCHEMA = {"$id": "events", "version": 1}
    return dict(_EVENT_SCHEMA or {})


def _validate_event(e: Mapping[str, Any]) -> Mapping[str, Any]:
    # Minimal validator honoring contracts without external libs
    et = str(e.get("type") or "").lower()
    if et not in {"track", "identify", "alias", "group"}:
        raise HTTPException(400, f"unsupported event type '{et}'")
    uid = e.get("user_id") or e.get("userId") or e.get("anonymous_id") or e.get("anonymousId")
    if et != "alias" and not uid:
        raise HTTPException(400, "user_id or anonymous_id is required")
    if et == "track":
        if not e.get("event"):
            raise HTTPException(400, "track requires 'event'")
        if not isinstance(e.get("properties", {}), dict):
            raise HTTPException(400, "track.properties must be object")
    elif et == "identify":
        if (not isinstance(e.get("traits", {}), dict)) and (not isinstance(e.get("consent", {}), dict)):
            raise HTTPException(400, "identify requires traits and/or consent object")
    elif et == "alias":
        if not e.get("previous_id") and not e.get("previousId"):
            raise HTTPException(400, "alias requires previous_id")
        if not e.get("user_id") and not e.get("userId"):
            raise HTTPException(400, "alias requires user_id")
    elif et == "group":
        if not e.get("group_id") and not e.get("groupId"):
            raise HTTPException(400, "group requires group_id")
        if not isinstance(e.get("traits", {}), dict):
            raise HTTPException(400, "group.traits must be object")
    # Normalize keys to snake_case to persist
    out: Dict[str, Any] = {}
    for k, v in e.items():
        nk = k
        if k.endswith("Id"):
            nk = k[:-2] + "_id"
        if k == "anonymousId":
            nk = "anonymous_id"
        if k == "userId":
            nk = "user_id"
        if k == "groupId":
            nk = "group_id"
        out[nk] = v
    if "type" in out:
        out["type"] = str(out["type"]).lower()
    return out


@router.post("/events/ingest")
def ingest_events(body: EventIngestBody, db: Session = Depends(get_db)):
    # Load schema (not strictly enforced, but returned for clients)
    schema = _load_event_schema()
    provider = registry().get("cdp")
    ingested = 0
    for raw in list(body.events or []):
        ev = _validate_event(raw)
        uid = str(ev.get("user_id") or ev.get("anonymous_id") or "")
        if not uid and ev.get("type") != "alias":
            # extra guard
            raise HTTPException(400, "missing user_id")
        # Persist append-only
        row = CDPEvent(
            id=str(uuid.uuid4()),
            tenant_id=body.tenant_id or "tenant",
            project_id=body.project_id or "project",
            run_id=body.run_id,
            user_id=uid or "-",
            event_type=str(ev.get("type")),
            payload=dict(ev),
        )
        db.add(row)
        # Call provider side-effects respecting contracts
        et = row.event_type
        if et == "track":
            provider.ingest_event({"user_id": uid, "event": ev.get("event"), "properties": ev.get("properties", {})})
        elif et == "identify":
            prof = {"user_id": uid, "traits": dict(ev.get("traits", {})), "consent": dict(ev.get("consent", {}))}
            provider.upsert_profile(prof)
        elif et == "alias":
            provider.upsert_profile({"user_id": uid, "alias": ev.get("previous_id") or ev.get("previousId")})
        elif et == "group":
            provider.ingest_event({"user_id": uid, "event": "group", "group_id": ev.get("group_id"), "traits": ev.get("traits", {})})
        ingested += 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "db error")
    return {"ok": True, "ingested": ingested, "schema_version": schema.get("version", 1)}


@router.post("/audiences/sync")
def audience_sync(body: AudienceSyncBody, db: Session = Depends(get_db)):
    provider = registry().get("cdp")
    start = time.time()
    res = provider.sync_audience({"name": body.name, "members": list(body.members or []), "meta": dict(body.meta or {})})
    job_id = str(res.get("id") or uuid.uuid4())
    row = AudienceSyncJob(id=job_id, audience={"name": body.name, "size": len(body.members or [])}, status="completed", result=dict(res))
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
    latency_ms = int((time.time() - start) * 1000)
    return {"job_id": job_id, "status": row.status, "metrics": {"capability": "cdp", "adapter": "mock_cdp", "latency_ms": latency_ms, "attempts": 1}}


@router.get("/profile/{user_id}")
def get_profile(user_id: str):
    provider = registry().get("cdp")
    prof = provider.get_profile(user_id)
    if not prof:
        raise HTTPException(404, "profile not found")
    # Never log or return secrets
    return {"user_id": user_id, "traits": dict(prof.get("traits", {})), "consent": dict(prof.get("consent", {})), "predictions": dict(prof.get("predictions", {}))}


