from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContractCoverageReport
from ..quality.contracts import compute_contract_coverage


router = APIRouter(prefix="", tags=["quality"])


class ContractsBody(BaseModel):
    tenant_id: str | None = None
    project_id: str | None = None
    run_id: str | None = None
    seed: int = 123


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


@router.post("/quality/contracts/report")
def contracts_report(body: ContractsBody, db: Session = Depends(get_db)):
    report = compute_contract_coverage(db, tenant_id=body.tenant_id, project_id=body.project_id, run_id=body.run_id, seed=body.seed)
    # persist DB
    try:
        db.add(ContractCoverageReport(id=str(uuid.uuid4()), report=report))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    # persist artifact
    out_path = os.path.join("apps", "orchestrator", "orchestrator", "quality", "contracts_report.json")
    _write_json(out_path, report)
    return report


