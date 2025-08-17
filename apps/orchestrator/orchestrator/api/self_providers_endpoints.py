from __future__ import annotations

import os
import time
import uuid
import json
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProviderConformanceReport
from ..providers.registry import registry
from ..security import audit_event
from ..providers.scaffold.generator import (
    generate_adapter_skeleton,
    ensure_providers_yaml_registration,
    write_mock_conformance_report,
)


router = APIRouter(prefix="/self/providers", tags=["self-providers"])


CapabilityType = Literal[
    "ads",
    "lifecycle",
    "experiments",
    "cdp",
    "vectorstore",
    "observability",
    "llm_gateway",
]


class ProviderScaffoldBody(BaseModel):
    capability: CapabilityType = Field(examples=["ads"])
    vendor: str = Field(examples=["acme_ads"])
    config: Dict[str, Any] = Field(default_factory=dict)
    activate: bool = False
    dry_run: bool = True
    seed: int = 123
    run_id: Optional[str] = None


def _cap_alias(cap: str) -> str:
    # Map friendly to registry/config canonical keys
    return "llm_observability" if cap == "observability" else cap


def _write_json_sorted(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = json.dumps(data, sort_keys=True) + "\n"
    try:
        cur = None
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if content != cur:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


@router.post("/scaffold")
def providers_scaffold(body: ProviderScaffoldBody, db: Session = Depends(get_db)):
    started = int(time.time() * 1000)
    cap = _cap_alias(body.capability)
    vendor = body.vendor.strip()
    if not vendor or any(ch in vendor for ch in "/\\. "):
        raise HTTPException(400, "invalid vendor key")

    # 1) Generate adapter skeleton + unit test skeleton
    gen = generate_adapter_skeleton(capability=cap, vendor=vendor, config=body.config)

    # 2) Register in providers.yaml (idempotent). Only add under adapters: map; don't activate unless requested
    cfg_path, applied_activation = ensure_providers_yaml_registration(
        vendor=vendor,
        capability=cap,
        activate=bool(body.activate),
    )

    # 3) Run local conformance (mocked, deterministic) and persist artifact
    report = write_mock_conformance_report(capability=cap, vendor=vendor, seed=int(body.seed))

    # 4) Persist DB ProviderConformanceReport rows (one per report)
    try:
        row = ProviderConformanceReport(
            id=str(uuid.uuid4()),
            capability=str(report.get("reports", [{}])[0].get("capability", cap)),
            adapter=str(report.get("reports", [{}])[0].get("adapter", vendor)),
            report=dict(report),
        )
        db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # 5) Optionally refresh registry mapping when activated
    if applied_activation:
        try:
            registry().reload()
        except Exception:
            pass

    took_ms = int(time.time() * 1000) - started
    out = {
        "status": "ok",
        "result_code": "ok",
        "capability": cap,
        "vendor": vendor,
        "adapter_path": gen["adapter_path"],
        "unit_test_path": gen["unit_test_path"],
        "config_path": cfg_path,
        "conformance_report_path": report.get("path"),
        "metrics": {"latency_ms": took_ms, "attempts": 1},
        "run_id": body.run_id or None,
        "activated": applied_activation,
        "dry_run": bool(body.dry_run),
    }

    try:
        audit_event(
            db,
            actor="api",
            event_type="self.providers.scaffold",
            request_id=f"self:providers:scaffold:{cap}:{vendor}",
            details=out,
        )
    except Exception:
        pass

    return out


