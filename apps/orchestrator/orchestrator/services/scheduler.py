from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import RunDB, SchedulerItem
from ..security import audit_event
from ..ai_graph.graph import start_graph_run


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except Exception:
        return default


def _env_true(key: str, default: str = "1") -> bool:
    try:
        v = os.getenv(key, default).strip().lower()
    except Exception:
        v = default
    return v not in {"0", "false", "no"}


@dataclass
class SchedulerPolicy:
    enabled: bool = True
    global_concurrency: int = 2
    tenant_max_active: int = 1
    queue_max: int = 100

    @classmethod
    def from_env(cls) -> "SchedulerPolicy":
        return cls(
            enabled=_env_true("SCHED_ENABLED", "1"),
            global_concurrency=_env_int("SCHED_CONCURRENCY", 2),
            tenant_max_active=_env_int("SCHED_TENANT_MAX_ACTIVE", 1),
            queue_max=_env_int("SCHED_QUEUE_MAX", 100),
        )


# Process-local policy and stats (deterministic; tests patch via API)
_POLICY: SchedulerPolicy = SchedulerPolicy.from_env()
_STATS: Dict[str, int] = {"leases": 0, "skipped_due_to_quota": 0, "completed": 0}

# Round-robin cursor per priority (deterministic across steps)
_RR_CURSOR: Dict[int, int] = {}


def get_policy() -> Dict[str, int | bool]:
    return {
        "enabled": _POLICY.enabled,
        "global_concurrency": _POLICY.global_concurrency,
        "tenant_max_active": _POLICY.tenant_max_active,
        "queue_max": _POLICY.queue_max,
    }


def patch_policy(db: Session, patch: Dict[str, int | bool]) -> Dict[str, int | bool]:
    global _POLICY
    enabled = patch.get("enabled")
    if isinstance(enabled, bool):
        _POLICY.enabled = enabled
    if isinstance(patch.get("global_concurrency"), int):
        _POLICY.global_concurrency = int(patch["global_concurrency"])  # type: ignore[index]
    if isinstance(patch.get("tenant_max_active"), int):
        _POLICY.tenant_max_active = int(patch["tenant_max_active"])  # type: ignore[index]
    if isinstance(patch.get("queue_max"), int):
        _POLICY.queue_max = int(patch["queue_max"])  # type: ignore[index]
    try:
        audit_event(db, actor="api", event_type="scheduler.policy", request_id="scheduler:policy", details={"policy": get_policy()})
    except Exception:
        pass
    return get_policy()


def get_stats() -> Dict[str, int]:
    return dict(_STATS)


def _sorted_queue(db: Session) -> List[SchedulerItem]:
    # SQL ORDER BY equivalent: priority DESC, enqueued_at ASC, run_id ASC
    rows = (
        db.query(SchedulerItem)
        .filter(SchedulerItem.state == "queued")
        .order_by(SchedulerItem.priority.desc(), SchedulerItem.enqueued_at.asc(), SchedulerItem.run_id.asc())
        .all()
    )
    return rows


def snapshot(db: Session) -> Dict[str, object]:
    q = _sorted_queue(db)
    active = db.query(SchedulerItem).filter(SchedulerItem.state == "active").count()
    completed = db.query(SchedulerItem).filter(SchedulerItem.state == "completed").count()
    items = [
        {
            "run_id": r.run_id,
            "tenant_id": r.tenant_id,
            "priority": r.priority,
            "state": r.state,
        }
        for r in q
    ]
    return {
        "queued": len(items),
        "active": int(active),
        "completed": int(completed),
        "items": items,
    }


def enqueue(db: Session, run_id: str, priority: Optional[int] = None) -> Dict[str, object]:
    if not _POLICY.enabled:
        return {"status": "disabled"}
    # Validate run exists
    run = db.get(RunDB, run_id)
    if not run:
        return {"error": "run not found"}

    # Idempotency: if exists, return exists
    row = db.get(SchedulerItem, run_id)
    if row:
        return {"status": "exists", "state": row.state, "priority": row.priority}

    # If run already in terminal state, skip enqueue
    if str(run.status) in {"succeeded", "blocked", "partial"}:
        return {"status": "skipped", "reason": "run already completed"}

    pri = int(priority) if isinstance(priority, int) else 0
    # Backpressure: enforce per-tenant + per-priority bucket deterministically
    queued_len = (
        db.query(SchedulerItem)
        .filter(
            SchedulerItem.state == "queued",
            SchedulerItem.priority == pri,
            SchedulerItem.tenant_id == run.tenant_id,
        )
        .count()
    )
    if queued_len >= _POLICY.queue_max:
        return {"error": "queue capacity exceeded", "queue_max": _POLICY.queue_max}
    item = SchedulerItem(run_id=run_id, tenant_id=run.tenant_id, priority=pri, state="queued")
    db.add(item)
    db.commit()
    try:
        audit_event(db, actor="api", event_type="scheduler.enqueue", run_id=run_id, request_id=f"{run_id}:enqueue", details={"priority": pri})
    except Exception:
        pass
    return {"status": "enqueued", "run_id": run_id, "priority": pri}


def _eligible_next(db: Session) -> Optional[Tuple[SchedulerItem, Dict[str, int]]]:
    # Respect global concurrency
    global_active = db.query(SchedulerItem).filter(SchedulerItem.state == "active").count()
    if global_active >= _POLICY.global_concurrency:
        _STATS["skipped_due_to_quota"] += 1
        return None

    # Build priority groups
    queued = _sorted_queue(db)
    if not queued:
        return None

    # Compute per-tenant active counts
    tenant_active: Dict[str, int] = {}
    for (tenant_id, cnt) in (
        db.query(SchedulerItem.tenant_id)
        .filter(SchedulerItem.state == "active")
        .all()
    ):
        tenant_active[tenant_id] = tenant_active.get(tenant_id, 0) + 1

    # Group queued by priority
    by_pri: Dict[int, List[SchedulerItem]] = {}
    for r in queued:
        by_pri.setdefault(r.priority, []).append(r)

    for pri in sorted(by_pri.keys(), reverse=True):
        bucket = by_pri[pri]
        # Unique tenants in order of first appearance
        ordered_tenants: List[str] = []
        seen: set[str] = set()
        for r in bucket:
            if r.tenant_id not in seen:
                seen.add(r.tenant_id)
                ordered_tenants.append(r.tenant_id)

        # Determine start index from round-robin cursor
        start_idx = _RR_CURSOR.get(pri, 0)
        n = len(ordered_tenants) if ordered_tenants else 0
        for k in range(n):
            t_idx = (start_idx + k) % n if n > 0 else 0
            tenant = ordered_tenants[t_idx] if n > 0 else None
            if tenant is None:
                break
            # Per-tenant cap
            if tenant_active.get(tenant, 0) >= _POLICY.tenant_max_active:
                continue
            # Pick first item for this tenant in this priority bucket
            for r in bucket:
                if r.tenant_id == tenant:
                    # Advance cursor for next call
                    _RR_CURSOR[pri] = (t_idx + 1) % n if n > 0 else 0
                    return (r, tenant_active)
        # If no tenant within this priority eligible, continue to next lower priority

    # No eligible item (blocked by quotas)
    _STATS["skipped_due_to_quota"] += 1
    return None


def step(db: Session) -> Dict[str, object]:
    if not _POLICY.enabled:
        return {"status": "disabled", **snapshot(db)}

    pick = _eligible_next(db)
    if not pick:
        return {"status": "no-op", **snapshot(db)}

    item, _tenant_active = pick
    # Lease: mark active
    row = db.get(SchedulerItem, item.run_id)
    if not row or row.state != "queued":
        return {"status": "stale", **snapshot(db)}
    row.state = "active"
    db.commit()
    _STATS["leases"] += 1
    try:
        audit_event(db, actor="api", event_type="scheduler.step", run_id=item.run_id, request_id=f"{item.run_id}:lease", details={"leased": item.run_id, "priority": item.priority})
    except Exception:
        pass

    # Synchronously start
    try:
        start_graph_run(db, item.run_id)
    except Exception:
        # Record as completed regardless; errors are reflected in run status
        pass

    # Transition to completed
    try:
        row2 = db.get(SchedulerItem, item.run_id)
        if row2:
            row2.state = "completed"
            db.commit()
            _STATS["completed"] += 1
    except Exception:
        db.rollback()

    snap = snapshot(db)
    snap.update({"leased": item.run_id, "status": "ok"})
    return snap


