from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from sqlalchemy.orm import Session

from ..db import get_db
from ..services.preview import PreviewService, DeployInput
from ..security import audit_event


router = APIRouter()


class DeployBody(BaseModel):
    owner: str = Field(examples=["octo-org"])
    repo: str = Field(examples=["sample-repo"])
    branch: str = Field(examples=["feature/add-preview"])
    base_url: Optional[str] = Field(default=None, examples=["http://preview.local"])
    force: bool = False


class SmokeBody(BaseModel):
    timeout_ms: int = Field(default=1000, ge=1, le=60000)
    inject_fail: bool = False


@router.post("/integrations/preview/{run_id}/deploy")
def preview_deploy(run_id: str, body: DeployBody, db: Session = Depends(get_db)):
    svc = PreviewService()
    try:
        res = svc.deploy(
            db,
            DeployInput(
                run_id=run_id,
                owner=body.owner,
                repo=body.repo,
                branch=body.branch,
                base_url=body.base_url,
                force=body.force,
            ),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Audit (idempotent on request_id)
    try:
        audit_event(
            db,
            actor="api",
            event_type="preview.deploy",
            run_id=run_id,
            project_id=None,
            request_id=f"{run_id}:preview:deploy",
            details={"owner": body.owner, "repo": body.repo, "branch": body.branch, "result": res},
        )
    except Exception:
        pass
    return res


@router.post("/integrations/preview/{run_id}/smoke")
def preview_smoke(run_id: str, body: SmokeBody, db: Session = Depends(get_db)):
    svc = PreviewService()
    try:
        res = svc.smoke(db, run_id, timeout_ms=body.timeout_ms, inject_fail=body.inject_fail)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Audit
    try:
        audit_event(
            db,
            actor="api",
            event_type="preview.smoke",
            run_id=run_id,
            project_id=None,
            request_id=f"{run_id}:preview:smoke",
            details={"timeout_ms": body.timeout_ms, "inject_fail": body.inject_fail, "result": res},
        )
    except Exception:
        pass
    return res


@router.get("/integrations/preview/{run_id}")
def preview_get(run_id: str, db: Session = Depends(get_db)):
    svc = PreviewService()
    try:
        res = svc.get_info(db, run_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    return res


