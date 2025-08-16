from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from ..models import GraphState


def record_step(
    db: Session,
    run_id: str,
    step_index: int,
    step_name: str,
    status: str,
    state_json: Dict[str, Any],
    attempt: int,
    logs_json: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    row = GraphState(
        id=str(uuid.uuid4()),
        run_id=run_id,
        step_index=step_index,
        step_name=step_name,
        status=status,
        attempt=attempt,
        state_json=state_json or {},
        logs_json=logs_json,
        error=error,
    )
    db.add(row)
    db.commit()


def get_last(db: Session, run_id: str) -> Optional[GraphState]:
    return (
        db.query(GraphState)
        .filter(GraphState.run_id == run_id)
        .order_by(desc(GraphState.step_index), desc(GraphState.attempt))
        .first()
    )


def get_history(db: Session, run_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.query(GraphState)
        .filter(GraphState.run_id == run_id)
        .order_by(asc(GraphState.step_index), asc(GraphState.attempt))
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "run_id": r.run_id,
                "step_index": r.step_index,
                "step_name": r.step_name,
                "status": r.status,
                "attempt": r.attempt,
                "created_at": r.created_at,
                "error": r.error,
                # Phase 14: include per-attempt duration from logs (ms)
                "duration_ms": int((r.logs_json or {}).get("duration_ms") or 0),
            }
        )
    return out


