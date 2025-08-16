from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from ..db import Base
from ..integrations.github import CTX_ARTIFACTS, CTX_DOR
from ..integrations.github import COMMENT_MARKER_PREFIX  # for marker naming parity
from ..integrations.github import _write_enabled as _gh_write_enabled  # reuse env gate

from ..blueprints.registry import registry
from ..ai_graph.repo import record_step
from ..models import GraphState


class ScaffoldStepRow(Base):
    __tablename__ = "scaffold_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    op_id: Mapped[str] = mapped_column(String(64))  # run_id or provided op id
    blueprint_id: Mapped[str] = mapped_column(String(128))
    step_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|completed|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("op_id", "blueprint_id", "step_name", name="uq_scaffold_step_unique"),
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class TargetRepo:
    mode: str  # new_repo | existing_repo
    owner: str
    name: str
    default_branch: str = "main"


def _env_or(val: Optional[str], env_key: str, default: str = "") -> str:
    if val:
        return val
    return os.getenv(env_key, default)


def _dry_run() -> bool:
    # Dry-run if GH writes are disabled
    return not _gh_write_enabled()


def ensure_tables(db: Session) -> None:
    # Ensure our table exists
    Base.metadata.create_all(bind=db.get_bind())


def _upsert_ledger(
    db: Session, *, op_id: str, blueprint_id: str, step: str, status: str, error: Optional[str] = None
) -> Tuple[str, int]:
    from uuid import uuid4
    # Try fetch existing row for idempotency
    row = (
        db.query(ScaffoldStepRow)
        .filter(ScaffoldStepRow.op_id == op_id, ScaffoldStepRow.blueprint_id == blueprint_id, ScaffoldStepRow.step_name == step)
        .first()
    )
    if row:
        # Update only if status is not completed
        if row.status != "completed":
            row.status = status
            row.attempts = int(row.attempts or 0) + 1
            row.error = error
            db.commit()
        return row.id, row.attempts
    # Insert new
    row = ScaffoldStepRow(
        id=str(uuid4()), op_id=op_id, blueprint_id=blueprint_id, step_name=step, status=status, attempts=1, error=error
    )
    db.add(row)
    db.commit()
    return row.id, row.attempts


def _simulate_pr_summary_payload(
    *, blueprint_id: str, blueprint_name: str, version: str, steps: List[Tuple[str, str, int]], dry_run: bool
) -> str:
    lines = [f"### AI‑CSuite App Factory Summary", "", f"Blueprint: {blueprint_id} — {blueprint_name} (v{version})", ""]
    lines.append("Steps executed:")
    for name, status, ts in steps:
        lines.append(f"- {name}: {status} @ {datetime.fromtimestamp(ts/1000.0).isoformat()}Z")
    if dry_run:
        lines.append("")
        lines.append("_Dry‑run: GitHub writes disabled (GITHUB_WRITE_ENABLED=0)_")
    lines.append("")
    # Marker uses a stable token so upsert behavior is deterministic across re-runs
    lines.append(f"<!-- {COMMENT_MARKER_PREFIX}:app-factory -->")
    return "\n".join(lines)


class ScaffolderService:
    def __init__(self) -> None:
        pass

    def run(
        self,
        db: Session,
        *,
        blueprint_id: str,
        op_id: str,
        target: TargetRepo,
        options: Optional[Dict] = None,
    ) -> Dict[str, object]:
        ensure_tables(db)
        bp = registry().get(blueprint_id)

        # Steps from manifest (authoritative ordering)
        steps_spec = [s.step for s in (bp.scaffold or [])]
        executed: List[Tuple[str, str, int]] = []

        # Validate minimal target fields
        owner = _env_or(target.owner, "E2E_REPO_OWNER")
        name = _env_or(target.name, "E2E_REPO_NAME")
        if target.mode == "existing_repo" and (not owner or not name) and not _dry_run():
            raise ValueError("owner and name are required for existing_repo mode")

        inject_step_name = (options or {}).get("inject_fail_step") if options else None

        # Simulate steps; on re-run, ledger prevents duplication
        for idx, step in enumerate(steps_spec):
            # mark running
            _, attempts_now = _upsert_ledger(db, op_id=op_id, blueprint_id=bp.id, step=step, status="running")
            # perform step (placeholder: deterministic no-op with sleep 0)
            # honor dry-run by not writing to network/FS; we only simulate effects
            error: Optional[str] = None
            try:
                # optional deterministic failure injection for tests (always fail when requested)
                if inject_step_name == step:
                    _upsert_ledger(db, op_id=op_id, blueprint_id=bp.id, step=step, status="failed", error=f"Injected failure at {step}")
                    raise RuntimeError(f"Injected failure at {step}")
                # each step can have a deterministic micro-action later (Phase 18+)
                pass
            except Exception as e:  # pragma: no cover (not expected in CI)
                error = str(e)
                _upsert_ledger(db, op_id=op_id, blueprint_id=bp.id, step=step, status="failed", error=error)
                raise
            # mark completed idempotently
            _upsert_ledger(db, op_id=op_id, blueprint_id=bp.id, step=step, status="completed")
            # Also record into existing graph history table for visibility
            try:
                # skip if already recorded to satisfy unique constraint
                exists = (
                    db.query(GraphState)
                    .filter(GraphState.run_id == op_id, GraphState.step_index == idx, GraphState.attempt == 1)
                    .first()
                )
                if not exists:
                    record_step(
                        db,
                        run_id=op_id,
                        step_index=idx,
                        step_name=step,
                        status="ok",
                        state_json={"op_id": op_id, "blueprint_id": bp.id, "step": step},
                        attempt=1,
                        logs_json={"scaffolder": True},
                        error=None,
                    )
            except Exception:
                pass
            executed.append((step, "completed", _now_ms()))

        # Build PR artifacts simulation and statuses staging when PRs enabled
        pr_summary = _simulate_pr_summary_payload(
            blueprint_id=bp.id,
            blueprint_name=bp.name,
            version=bp.version,
            steps=executed,
            dry_run=_dry_run(),
        )

        # Stage statuses: reuse our known contexts and include a placeholder for preview smoke
        staged_statuses = [
            {"context": CTX_DOR, "state": "success"},
            {"context": CTX_ARTIFACTS, "state": "success"},
            {"context": "ai-csuite/preview-smoke", "state": "pending"},
        ]

        return {
            "blueprint": {"id": bp.id, "name": bp.name, "version": bp.version},
            "op_id": op_id,
            "target": {"mode": target.mode, "owner": owner, "name": name, "default_branch": target.default_branch},
            "steps": executed,
            "pr_summary": pr_summary,
            "staged_statuses": staged_statuses,
            "dry_run": _dry_run(),
        }


