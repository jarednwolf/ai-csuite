from __future__ import annotations

import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SSOConfig, EnterpriseRole, AuditEvent
from ..sso_mock import validate_config
from ..security import audit_event
from ..rbac import scopes_for_role, require_scope


router = APIRouter(prefix="", tags=["enterprise"])


class SSOConfigBody(BaseModel):
    tenant_id: str
    protocol: str  # oidc|saml
    config: Dict


@router.post("/auth/sso/config")
def auth_sso_config(body: SSOConfigBody, db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "write:enterprise"):
        raise HTTPException(403, "forbidden")
    res = validate_config(body.protocol, body.config)
    if not res.get("ok"):
        raise HTTPException(400, res)
    row = SSOConfig(id=str(uuid.uuid4()), tenant_id=body.tenant_id, protocol=body.protocol.lower().strip(), config=res.get("normalized", {}))
    db.add(row)
    db.commit()
    try:
        audit_event(db, actor="api", event_type="sso.config", request_id=f"sso:{row.id}", details={"tenant_id": body.tenant_id, "protocol": body.protocol})
    except Exception:
        pass
    return {"status": "ok", "config_id": row.id}


@router.get("/audit/export")
def audit_export(tenant_id: Optional[str] = Query(default=None), fmt: str = Query("json"), db: Session = Depends(get_db), x_role: str | None = Header(default=None, alias="X-Role")):
    scopes = scopes_for_role(x_role or "admin")
    if not require_scope(scopes, "read:enterprise"):
        raise HTTPException(403, "forbidden")
    q = db.query(AuditEvent)
    if tenant_id:
        q = q.filter(AuditEvent.tenant_id == tenant_id)
    rows = q.order_by(AuditEvent.ts.asc()).all()
    if fmt not in {"json", "csv"}:
        raise HTTPException(400, "unsupported format")
    if fmt == "json":
        out = [
            {"ts": r.ts.isoformat(), "tenant_id": r.tenant_id, "user_id": r.user_id, "action": r.action, "payload": r.payload}
            for r in rows
        ]
        return {"items": out}
    # csv
    lines = ["ts,tenant_id,user_id,action,payload\n"]
    for r in rows:
        payload = str(r.payload).replace("\n", " ").replace(",", ";")
        lines.append(f"{r.ts.isoformat()},{r.tenant_id or ''},{r.user_id or ''},{r.action},{payload}\n")
    return {"text": "".join(lines)}


