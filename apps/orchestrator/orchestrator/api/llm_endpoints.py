from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ..providers.registry import registry, _models_policy_path


router = APIRouter(prefix="/llm", tags=["llm"])


class RouteTestBody(BaseModel):
    input: str
    tags: List[str] = []


@router.post("/route/test")
def route_test(body: RouteTestBody):
    gw = registry().get("llm_gateway")
    return gw.route(body.input, body.tags)


@router.get("/models")
def list_models():
    gw = registry().get("llm_gateway")
    return gw.models()


class PolicyUpdateBody(BaseModel):
    weights: dict
    constraints: Optional[dict] = None


@router.post("/policy/update")
def policy_update(body: PolicyUpdateBody):
    path = _models_policy_path()
    try:
        content = {"weights": dict(body.weights), "constraints": dict(body.constraints or {})}
        # validate minimal schema
        for k in ["cost", "latency", "quality", "safety"]:
            if k not in content["weights"]:
                raise ValueError("missing weight: " + k)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(content, sort_keys=True))
            f.write("\n")
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "path": path}


