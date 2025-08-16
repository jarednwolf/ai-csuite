from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import List

from ..blueprints.registry import registry
from ..blueprints.models import BlueprintSummary, BlueprintManifest


router = APIRouter()


@router.get("/blueprints", response_model=List[BlueprintSummary])
def list_blueprints():
    try:
        reg = registry()
    except Exception as e:
        # Startup should have loaded already; still surface a clean error if not
        raise HTTPException(500, f"registry error: {e}")
    return reg.list()


@router.get("/blueprints/{blueprint_id}", response_model=BlueprintManifest)
def get_blueprint(blueprint_id: str):
    reg = registry()
    try:
        return reg.get(blueprint_id)
    except KeyError:
        raise HTTPException(404, f"blueprint '{blueprint_id}' not found")


