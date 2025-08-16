from __future__ import annotations

from typing import Dict, Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import uuid

from sqlalchemy.orm import Session
from fastapi import Depends

from ..db import get_db
from ..services.scaffolder import ScaffolderService, TargetRepo
from ..blueprints.registry import registry
from ..integrations.github import _write_enabled as _gh_write_enabled


router = APIRouter()


class TargetModel(BaseModel):
    mode: Literal["new_repo", "existing_repo"] = Field(examples=["existing_repo"])
    owner: Optional[str] = None
    name: Optional[str] = None
    default_branch: str = "main"


class ScaffoldBody(BaseModel):
    blueprint_id: str = Field(examples=["web-crud-fastapi-postgres-react"])
    target: TargetModel
    run_id: Optional[str] = Field(default=None, description="Optional op/run id for idempotency linkage")
    options: Optional[Dict] = None


@router.post("/app-factory/scaffold")
def app_factory_scaffold(body: ScaffoldBody, db: Session = Depends(get_db)):
    # Validate blueprint exists first for clear 404
    try:
        _ = registry().get(body.blueprint_id)
    except KeyError:
        raise HTTPException(404, f"unknown blueprint '{body.blueprint_id}'")

    # Validate target
    if body.target.mode == "existing_repo":
        if not (body.target.owner or body.target.name):
            # In dry-run we allow missing owner/name for simulation
            if _gh_write_enabled():
                raise HTTPException(400, "owner and name are required for existing_repo mode")

    op_id = body.run_id or str(uuid.uuid4())
    svc = ScaffolderService()
    try:
        result = svc.run(
            db,
            blueprint_id=body.blueprint_id,
            op_id=op_id,
            target=TargetRepo(
                mode=body.target.mode,
                owner=body.target.owner or "",
                name=body.target.name or "",
                default_branch=body.target.default_branch or "main",
            ),
            options=body.options or {},
        )
    except Exception as e:
        raise HTTPException(400, str(e))
    return result


