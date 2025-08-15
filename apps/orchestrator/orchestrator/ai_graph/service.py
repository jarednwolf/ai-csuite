from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple, Optional
from sqlalchemy.orm import Session

from .repo import record_step, get_last
from ..models import GraphState


def with_retry(func: Callable[[], Any], *, max_attempts: int = 3, base_delay: float = 0.02, backoff: float = 2.0):
    attempt = 0
    while True:
        attempt += 1
        try:
            return func()
        except Exception:
            if attempt >= max_attempts:
                raise
            time.sleep(base_delay * (backoff ** (attempt - 1)))


def persist_on_step(
    db: Session,
    run_id: str,
    step_index: int,
    step_name: str,
    status: str,
    state: Dict[str, Any],
    attempt: int,
    error: Optional[str] = None,
    logs: Optional[Dict[str, Any]] = None,
) -> None:
    # Minimal snapshot only: keys relevant to resume and history
    snapshot = {
        "run_id": state.get("run_id"),
        "history": state.get("history", []),
        "prd": state.get("prd"),
        "design": state.get("design"),
        "research": state.get("research"),
        "plan": state.get("plan"),
        "code_patch": state.get("code_patch"),
        "tests_result": state.get("tests_result"),
        "pr_info": state.get("pr_info"),
        # Normalize attempts to an integer for safe resume
        "qa_attempts": int(state.get("qa_attempts") or 0),
        # Phase 12: persist shared memory across personas
        "shared_memory": state.get("shared_memory", {}),
    }
    record_step(
        db,
        run_id=run_id,
        step_index=step_index,
        step_name=step_name,
        status=status,
        state_json=snapshot,
        attempt=attempt,
        logs_json=logs,
        error=error,
    )


def resume_from_last(db: Session, run_id: str) -> Tuple[Dict[str, Any], int]:
    last = get_last(db, run_id)
    if not last:
        return ({"run_id": run_id, "history": [], "shared_memory": {"notes": []}}, 0)
    state = dict(last.state_json or {})
    state["run_id"] = run_id
    # Normalize attempts on resume
    state["qa_attempts"] = int(state.get("qa_attempts") or 0)
    # Ensure shared_memory present for Phase 12 determinism
    if not isinstance(state.get("shared_memory"), dict):
        state["shared_memory"] = {"notes": []}
    else:
        state.setdefault("shared_memory", {}).setdefault("notes", [])
    history = state.get("history", [])
    # Compute next_step_index from history length (maps to fixed order)
    order = ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]
    idx = 0
    # Consume the canonical sequence once; allow repeated qa/engineer after first qa
    for name in history:
        if idx < len(order) and order[idx] == name:
            idx += 1
        elif name in {"qa", "engineer"} and idx >= order.index("qa") and idx < len(order)-1:
            # Do not advance index for backtrack loop entries; they don't move past qa until success
            pass
    return (state, idx)


def compute_run_metrics(db: Session, run_id: str) -> Dict[str, Any]:
    rows = (
        db.query(GraphState)
        .filter(GraphState.run_id == run_id)
        .order_by(GraphState.step_index.asc(), GraphState.attempt.asc())
        .all()
    )
    steps: list[Dict[str, Any]] = []
    total_duration_ms = 0
    qa_attempts = 0
    for r in rows:
        logs = r.logs_json or {}
        duration_ms = int(logs.get("duration_ms") or 0)
        if r.status == "ok":
            total_duration_ms += duration_ms
        # capture latest qa_attempts from state snapshot
        try:
            qa_attempts = max(qa_attempts, int((r.state_json or {}).get("qa_attempts") or 0))
        except Exception:
            pass
        steps.append(
            {
                "step_index": r.step_index,
                "step_name": r.step_name,
                "status": r.status,
                "attempt": r.attempt,
                "duration_ms": duration_ms,
            }
        )
    # Simple deterministic cost model: 100 tokens per step attempt
    estimated_tokens = len(steps) * 100
    estimated_usd = round(estimated_tokens * 0.000002, 6)
    return {
        "run_id": run_id,
        "steps": steps,
        "totals": {
            "total_duration_ms": total_duration_ms,
            "qa_attempts": qa_attempts,
            "steps_count": len(steps),
        },
        "cost": {
            "estimated_tokens": estimated_tokens,
            "estimated_usd": estimated_usd,
        },
    }


