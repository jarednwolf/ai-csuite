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


# --- Phase 31–33: Provider state and reports ---
class ProviderState(Base):
    __tablename__ = "provider_state"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capability: Mapped[str] = mapped_column(Text)
    active_adapter: Mapped[str] = mapped_column(Text)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProviderConformanceReport(Base):
    __tablename__ = "provider_conformance_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capability: Mapped[str] = mapped_column(Text)
    adapter: Mapped[str] = mapped_column(Text)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProviderScaffold(Base):
    __tablename__ = "provider_scaffolds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capability: Mapped[str] = mapped_column(Text)
    vendor: Mapped[str] = mapped_column(Text)
    adapter_path: Mapped[str] = mapped_column(Text)
    unit_test_path: Mapped[str] = mapped_column(Text)
    config_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProviderShadowDiff(Base):
    __tablename__ = "provider_shadow_diffs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    shadow_id: Mapped[str] = mapped_column(String(36))
    capability: Mapped[str] = mapped_column(Text)
    candidate: Mapped[str] = mapped_column(Text)
    diff: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 34–39: Data/Experiments/Marketing Loop (append-only stores) ---
class CDPEvent(Base):
    __tablename__ = "cdp_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), default="tenant")
    project_id: Mapped[str] = mapped_column(String(36), default="project")
    run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(16))  # track|identify|alias|group
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cdp_events_user", "user_id"),
        Index("ix_cdp_events_type", "event_type"),
    )


class AudienceSyncJob(Base):
    __tablename__ = "audience_sync_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    audience: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|completed|failed
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExperimentState(Base):
    __tablename__ = "experiments_state"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(64), index=True)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BIInsight(Base):
    __tablename__ = "bi_insights"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    insights: Mapped[dict] = mapped_column(JSON, default=dict)
    suggestions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LifecycleSend(Base):
    __tablename__ = "lifecycle_sends"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(16))  # email|push|inapp
    recipient: Mapped[str] = mapped_column(String(256))
    message: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|sent|blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_lifecycle_recipient", "recipient"),
    )


class AdsCampaign(Base):
    __tablename__ = "ads_campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|paused|blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AttributionReport(Base):
    __tablename__ = "attribution_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 40: LLM Observability & Evals ---
class LLMTrace(Base):
    __tablename__ = "llm_traces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvalReportDB(Base):
    __tablename__ = "eval_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(String(64), default="default")
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 41: VectorStore indexes & Memory Policy ---
class VectorStoreIndex(Base):
    __tablename__ = "vectorstore_indexes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    adapter: Mapped[str] = mapped_column(String(64))
    index_name: Mapped[str] = mapped_column(String(64))
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 42: Safety & Autonomy ---
class SafetyAudit(Base):
    __tablename__ = "safety_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_type: Mapped[str] = mapped_column(String(32))  # creative|spend
    status: Mapped[str] = mapped_column(String(16))  # allowed|blocked|escalate
    findings: Mapped[dict] = mapped_column(JSON, default=dict)
    redacted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutonomySetting(Base):
    __tablename__ = "autonomy_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16))  # manual|limited|full
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BudgetCap(Base):
    __tablename__ = "budget_caps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cap_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 43–46: Planning, Billing, Enterprise ---
class PlanningValueScore(Base):
    __tablename__ = "planning_value_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(String(36))
    idea_id: Mapped[str] = mapped_column(String(64))  # roadmap_item_id or arbitrary idea key
    score: Mapped[int] = mapped_column(Integer)  # basis points for determinism
    rationale: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BillingUsage(Base):
    __tablename__ = "billing_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    meters: Mapped[dict] = mapped_column(JSON, default=dict)  # tokens,runs,preview_minutes,storage_mb,api_calls
    plan: Mapped[str] = mapped_column(String(16), default="community")  # community|hosted|enterprise
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_billing_usage_tenant_period"),
        Index("ix_billing_usage_tenant_period", "tenant_id", "period"),
    )


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    period: Mapped[str] = mapped_column(String(7))
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    line_items: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EnterpriseRole(Base):
    __tablename__ = "enterprise_roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    scopes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_enterprise_role_user"),
    )


class SSOConfig(Base):
    __tablename__ = "sso_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    protocol: Mapped[str] = mapped_column(String(16))  # oidc|saml
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Phase 47–52: Repo intelligence, quality, self-work (append-only stores) ---
class RepoMap(Base):
    __tablename__ = "repo_map"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    map: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RepoHotspot(Base):
    __tablename__ = "repo_hotspots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hotspots: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContractCoverageReport(Base):
    __tablename__ = "contracts_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpeculativeReport(Base):
    __tablename__ = "spec_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentReview(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(64), default="ai-csuite/self-review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

