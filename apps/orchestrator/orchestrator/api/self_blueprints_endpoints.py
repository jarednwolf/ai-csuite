from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

from ..blueprints.scaffold import scaffold_from_blueprint
from ..blueprints.registry import registry


router = APIRouter(prefix="/self/blueprints", tags=["self-blueprints"])


class BlueprintScaffoldBody(BaseModel):
    blueprint_id: str
    options: Dict[str, Any] | None = None


@router.post("/scaffold")
def blueprint_scaffold(body: BlueprintScaffoldBody):
    # Validate exists for clear error
    try:
        _ = registry().get(body.blueprint_id)
    except KeyError:
        raise HTTPException(404, f"unknown blueprint '{body.blueprint_id}'")
    return scaffold_from_blueprint(blueprint_id=body.blueprint_id)



