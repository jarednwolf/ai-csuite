from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean, JSON, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# Keep IDs as strings for cross-DB portability
ID = String(36)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    repo_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RoadmapItem(Base):
    __tablename__ = "roadmap_items"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="planned")  # planned|in_progress|blocked|done
    priority: Mapped[int] = mapped_column(Integer, default=100)
    target_release: Mapped[str] = mapped_column(String(64), default="")

class RunDB(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID)
    roadmap_item_id: Mapped[Optional[str]] = mapped_column(ID, nullable=True)
    phase: Mapped[str] = mapped_column(String(32), default="delivery")   # discovery|delivery|release
    status: Mapped[str] = mapped_column(String(32), default="pending")   # pending|running|succeeded|blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ---------- Discovery artifacts ----------
class PRD(Base):
    __tablename__ = "prds"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID)
    roadmap_item_id: Mapped[str] = mapped_column(ID)
    version: Mapped[str] = mapped_column(String(16), default="v0")
    prd_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DesignCheck(Base):
    __tablename__ = "design_checks"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID)
    roadmap_item_id: Mapped[str] = mapped_column(ID)
    passes: Mapped[bool] = mapped_column(Boolean, default=True)
    heuristics_score: Mapped[int] = mapped_column(Integer, default=90)  # 0..100
    a11y_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ResearchNote(Base):
    __tablename__ = "research_notes"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID)
    roadmap_item_id: Mapped[str] = mapped_column(ID)
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

from sqlalchemy import JSON as _JSON  # ensure JSON import exists for KbChunk

class KbChunk(Base):
    __tablename__ = "kb_chunks"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID)
    project_id: Mapped[str] = mapped_column(ID)
    kind: Mapped[str] = mapped_column(String(32))
    ref_id: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text)
    emb: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- GitHub PR metadata ---
class PullRequest(Base):
    __tablename__ = "pull_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(String(36))
    repo: Mapped[str] = mapped_column(String(200))  # "owner/repo"
    branch: Mapped[str] = mapped_column(String(200))
    number: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 11: Graph state persistence ---
class GraphState(Base):
    __tablename__ = "graph_states"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # ok|error
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    logs_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", "attempt", name="uq_graph_state_run_step_attempt"),
        Index("ix_graph_state_run", "run_id"),
    )


# --- Phase 19: Budget ledger ---
class BudgetUsage(Base):
    __tablename__ = "budget_usages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    persona: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # null for totals
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok|warn|blocked
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", "persona", name="uq_budget_run_persona"),
        Index("ix_budget_run", "run_id"),
    )


# --- Phase 23: Audit logs (append-only) ---
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    event_type: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), default="")
    details_redacted: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        # Idempotency on retries: same logical event may be written multiple times; dedupe by tuple
        UniqueConstraint("event_type", "run_id", "request_id", name="uq_audit_event_req"),
        Index("ix_audit_ts", "ts"),
        Index("ix_audit_event", "event_type"),
    )


# --- Phase 28: Scheduler queue (deterministic, offline-only) ---
class SchedulerItem(Base):
    __tablename__ = "scheduler_items"
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    state: Mapped[str] = mapped_column(String(16), default="queued", index=True)  # queued|active|completed
    enqueued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sched_state", "state"),
        Index("ix_sched_priority", "priority"),
        Index("ix_sched_tenant_state", "tenant_id", "state"),
    )
