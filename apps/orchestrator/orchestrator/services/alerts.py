from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session
from sqlalchemy import String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..models import GraphState, BudgetUsage, RunDB, PullRequest
from ..discovery import dor_check
from .preview import PreviewDeployRow
from ..integrations import github as gh


def _env_true(key: str, default: str = "1") -> bool:
    try:
        val = os.getenv(key, default).strip().lower()
    except Exception:
        val = default
    return val not in {"0", "false", "no"}


def _env_float(key: str, default: float) -> float:
    try:
        v = float(os.getenv(key, str(default)))
    except Exception:
        v = float(default)
    return v


def _env_int(key: str, default: int) -> int:
    try:
        v = int(os.getenv(key, str(default)))
    except Exception:
        v = int(default)
    return v


def _now() -> datetime:
    return datetime.utcnow()


class AlertRow(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    alert_type: Mapped[str] = mapped_column(String(64))
    key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="low")  # low|medium|high
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|cleared
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("run_id", "alert_type", "key", name="uq_alert_run_type_key"),
    )


def ensure_tables(db: Session) -> None:
    Base.metadata.create_all(bind=db.get_bind())


@dataclass
class Thresholds:
    window: int
    stuck_ms: int
    burn_pct: float
    retry_exhaust_max: int


def _defaults_from_env() -> Thresholds:
    return Thresholds(
        window=_env_int("ALERTS_WINDOW", 20),
        stuck_ms=_env_int("ALERTS_STUCK_MS", 30000),
        burn_pct=_env_float("ALERTS_SLO_BURN_PCT", 0.2),
        retry_exhaust_max=_env_int("ALERTS_RETRY_EXHAUST_MAX", 3),
    )


def _required_contexts() -> List[str]:
    # Reuse GitHub integration defaults (local-only proxies; no external calls)
    return gh._required_contexts()  # type: ignore[attr-defined]


class AlertsService:
    def __init__(self) -> None:
        pass

    # ---- Public API ----
    def compute(self, db: Session, run_id: str, *, overrides: Optional[Dict[str, float | int]] = None) -> Dict[str, object]:
        if not _env_true("ALERTS_ENABLED", "1"):
            raise ValueError("alerts disabled (ALERTS_ENABLED=0)")
        ensure_tables(db)

        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")

        th = _defaults_from_env()
        overrides = overrides or {}
        if "window" in overrides and overrides["window"]:
            th.window = int(overrides["window"])  # type: ignore
        if "stuck_ms" in overrides and overrides["stuck_ms"]:
            th.stuck_ms = int(overrides["stuck_ms"])  # type: ignore
        if "burn_pct" in overrides and overrides["burn_pct"] is not None:
            th.burn_pct = float(overrides["burn_pct"])  # type: ignore
        if "retry_exhaust_max" in overrides and overrides["retry_exhaust_max"]:
            th.retry_exhaust_max = int(overrides["retry_exhaust_max"])  # type: ignore

        # Compute SLOs & alerts
        slo, detected = self._determine_alerts(db, run_id, th)

        # Upsert ledger idempotently
        active_keys = set()
        for a in detected:
            key = a.get("key") or None
            self._upsert(db, run_id, a["type"], key, a.get("severity", "low"), a.get("message", ""), status="active")
            active_keys.add((a["type"], key))

        # Clear any non-active rows in this compute pass
        existing = db.query(AlertRow).filter(AlertRow.run_id == run_id).all()
        for row in existing:
            pair = (row.alert_type, row.key)
            if pair not in active_keys and row.status != "cleared":
                row.status = "cleared"
                row.attempts = int(row.attempts or 0) + 1
                row.updated_at = _now()
                db.commit()

        status = "ok" if len(detected) == 0 else "alerts"

        # Publish status to GitHub (or dry-run simulation)
        publish = self._publish_status_and_summary(db, run_id, status=status, slo=slo, alerts=detected)

        result: Dict[str, object] = {
            "run_id": run_id,
            "status": status,
            "thresholds": {
                "window": th.window,
                "stuck_ms": th.stuck_ms,
                "burn_pct": th.burn_pct,
                "retry_exhaust_max": th.retry_exhaust_max,
            },
            "slo": slo,
            "alerts": detected,
            "updated_at": _now().isoformat() + "Z",
        }
        # Surface dry-run status/summary for tests
        if publish.get("dry_run"):
            if publish.get("status"):
                result.setdefault("statuses", []).append(publish["status"])  # type: ignore
            if publish.get("summary"):
                result["summary"] = publish["summary"]
        return result

    def get_snapshot(self, db: Session, run_id: str) -> Dict[str, object]:
        if not _env_true("ALERTS_ENABLED", "1"):
            raise ValueError("alerts disabled (ALERTS_ENABLED=0)")
        ensure_tables(db)
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")
        rows = (
            db.query(AlertRow)
            .filter(AlertRow.run_id == run_id)
            .order_by(AlertRow.updated_at.desc())
            .all()
        )
        active = [self._row_to_alert(r) for r in rows if r.status == "active"]
        status = "ok" if len(active) == 0 else "alerts"
        th = _defaults_from_env()
        return {
            "run_id": run_id,
            "status": status,
            "thresholds": {
                "window": th.window,
                "stuck_ms": th.stuck_ms,
                "burn_pct": th.burn_pct,
                "retry_exhaust_max": th.retry_exhaust_max,
            },
            "alerts": active,
            "updated_at": (rows[0].updated_at.isoformat() + "Z") if rows else None,
        }

    def reset(self, db: Session, run_id: str) -> Dict[str, object]:
        if not _env_true("ALERTS_ENABLED", "1"):
            raise ValueError("alerts disabled (ALERTS_ENABLED=0)")
        ensure_tables(db)
        count = db.query(AlertRow).filter(AlertRow.run_id == run_id).delete()
        try:
            db.commit()
        except Exception:
            db.rollback()
        return {"deleted": int(count or 0)}

    # ---- Internals ----
    def _row_to_alert(self, r: AlertRow) -> Dict[str, str]:
        out = {"type": r.alert_type, "severity": r.severity, "message": r.message}
        if r.key:
            out["key"] = r.key
        return out

    def _upsert(self, db: Session, run_id: str, alert_type: str, key: Optional[str], severity: str, message: str, *, status: str) -> None:
        row = (
            db.query(AlertRow)
            .filter(AlertRow.run_id == run_id, AlertRow.alert_type == alert_type, AlertRow.key == key)
            .first()
        )
        if row:
            row.severity = severity
            row.message = message
            row.status = status
            row.attempts = int(row.attempts or 0) + 1
            row.updated_at = _now()
            db.commit()
        else:
            new_row = AlertRow(
                id=str(uuid.uuid4()),
                run_id=run_id,
                alert_type=alert_type,
                key=key,
                severity=severity,
                message=message,
                status=status,
                attempts=1,
                updated_at=_now(),
            )
            db.add(new_row)
            db.commit()

    def _determine_alerts(self, db: Session, run_id: str, th: Thresholds) -> Tuple[Dict[str, object], List[Dict[str, str]]]:
        # Load recent history for SLOs and retry conditions
        rows = (
            db.query(GraphState)
            .filter(GraphState.run_id == run_id)
            .order_by(GraphState.step_index.asc(), GraphState.attempt.asc())
            .all()
        )
        # SLO: error burn over window
        flat: List[Tuple[str, int, str]] = []  # (step_name, attempt, status)
        for r in rows:
            flat.append((r.step_name, r.attempt, r.status))
        last_n = flat[-th.window:] if th.window > 0 else flat
        total = max(len(last_n), 1)
        err = sum(1 for _, _, st in last_n if st == "error")
        error_ratio = err / total

        # SLO: retry success rate among retried steps
        by_step: Dict[int, List[GraphState]] = {}
        for r in rows:
            by_step.setdefault(r.step_index, []).append(r)
        retried_steps = 0
        retried_success = 0
        retry_exhaust_alerts: List[Dict[str, str]] = []
        for idx, items in by_step.items():
            # Sort by attempt
            items.sort(key=lambda x: x.attempt)
            max_attempt = items[-1].attempt
            last_status = items[-1].status
            if max_attempt > 1:
                retried_steps += 1
                if last_status == "ok":
                    retried_success += 1
            # Retry exhaust detection (max attempts and still error)
            if max_attempt >= th.retry_exhaust_max and last_status == "error":
                step_name = items[-1].step_name
                retry_exhaust_alerts.append({
                    "type": "retry_exhaust",
                    "key": f"{idx}:{step_name}",
                    "severity": "high",
                    "message": f"Step {step_name} exhausted retries ({max_attempt}) and failed",
                })

        retry_success_rate = (retried_success / retried_steps) if retried_steps > 0 else 1.0

        # PR gating adherence/stuck
        gating = self._compute_pr_gating_state(db, run_id)
        stuck_alerts: List[Dict[str, str]] = []
        if gating and gating.get("has_pr") and (not gating.get("all_green")):
            # Consider stuck if PR is older than threshold
            pr_created: Optional[datetime] = gating.get("pr_created_at")  # type: ignore
            if pr_created is not None:
                age_ms = int((_now() - pr_created).total_seconds() * 1000)
                if age_ms >= th.stuck_ms:
                    not_green_list: List[str] = gating.get("not_green", [])  # type: ignore
                    stuck_alerts.append({
                        "type": "pr_gating_stuck",
                        "severity": "medium",
                        "message": f"PR gating not green: {', '.join(not_green_list)}",
                    })

        # Budget overflow (Phase 19 ledger)
        budget_alerts: List[Dict[str, str]] = []
        bu_rows = (
            db.query(BudgetUsage)
            .filter(BudgetUsage.run_id == run_id)
            .all()
        )
        for r in bu_rows:
            if (r.persona is None) and (r.status == "blocked"):
                budget_alerts.append({
                    "type": "budget_overflow",
                    "key": "totals",
                    "severity": "high",
                    "message": "Budget status is blocked",
                })
            if (r.persona is not None) and (r.status == "blocked"):
                budget_alerts.append({
                    "type": "budget_overflow",
                    "key": f"persona:{r.persona}",
                    "severity": "high",
                    "message": f"Persona '{r.persona}' blocked by budget",
                })

        alerts: List[Dict[str, str]] = []
        if error_ratio > th.burn_pct:
            alerts.append({
                "type": "slo_burn",
                "severity": "medium",
                "message": f"Error ratio {error_ratio:.2f} over last {len(last_n)} attempts exceeds {th.burn_pct:.2f}",
            })
        alerts.extend(retry_exhaust_alerts)
        alerts.extend(stuck_alerts)
        alerts.extend(budget_alerts)

        slo = {
            "window": th.window,
            "error_ratio": round(error_ratio, 4),
            "retry_success_rate": round(retry_success_rate, 4),
            "pr_contexts_green": bool(gating.get("all_green")) if gating else None,
        }
        return slo, alerts

    def _compute_pr_gating_state(self, db: Session, run_id: str) -> Optional[Dict[str, object]]:
        # Evaluate required contexts using local-only proxies; only when a PR exists
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.run_id == run_id)
            .order_by(PullRequest.created_at.desc())
            .first()
        )
        if not pr:
            return None
        req = _required_contexts()
        state_map: Dict[str, bool] = {}

        # DOR: compute via dor_check
        run = db.get(RunDB, run_id)
        ok_dor, _, _ = dor_check(db, run.tenant_id, run.project_id, run.roadmap_item_id) if run else (True, [], {})
        state_map[gh.CTX_DOR] = bool(ok_dor)

        # ARTIFACTS: consider present when PR exists
        state_map[gh.CTX_ARTIFACTS] = True

        # HUMAN: local proxy unknown -> not green (remains pending) unless context not required
        state_map[gh.CTX_HUMAN] = False

        # PREVIEW: consult preview ledger for this run
        prev = db.query(PreviewDeployRow).filter(PreviewDeployRow.run_id == run_id).first()
        state_map[gh.CTX_PREVIEW] = (prev is not None and prev.status == "success")

        # BUDGET: consult totals row
        totals = (
            db.query(BudgetUsage)
            .filter(BudgetUsage.run_id == run_id, BudgetUsage.persona == None)  # noqa: E711
            .first()
        )
        state_map[gh.CTX_BUDGET] = (totals is None) or (totals.status != "blocked")

        # Aggregate results only for required contexts
        not_green: List[str] = []
        for c in req:
            if state_map.get(c) is not True:
                not_green.append(c)
        all_green = (len(not_green) == 0)
        return {
            "has_pr": True,
            "pr_created_at": pr.created_at,
            "required_contexts": req,
            "not_green": not_green,
            "all_green": all_green,
        }

    def _build_ops_md(self, *, run: RunDB, slo: Dict[str, object], alerts: List[Dict[str, str]]) -> str:
        lines: List[str] = []
        lines.append("### Operations")
        lines.append("")
        lines.append("SLOs")
        lines.append(f"- Error ratio (last {slo.get('window')}): {slo.get('error_ratio')}")
        lines.append(f"- Retry success rate: {slo.get('retry_success_rate')}")
        if slo.get("pr_contexts_green") is not None:
            lines.append(f"- PR contexts green: {slo.get('pr_contexts_green')}")
        lines.append("")
        if alerts:
            lines.append("Active Alerts")
            for a in alerts:
                key = (" (" + a.get("key", "") + ")") if a.get("key") else ""
                lines.append(f"- {a['type']}{key}: {a.get('message','')}")
        else:
            lines.append("Active Alerts")
            lines.append("- None")
        return "\n".join(lines)

    def _publish_status_and_summary(self, db: Session, run_id: str, *, status: str, slo: Dict[str, object], alerts: List[Dict[str, str]]) -> Dict[str, object]:
        # Try to publish commit status on branch for PR or preview branch (dry-run aware)
        # 1) Determine branch coordinates (prefer PR; else preview)
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.run_id == run_id)
            .order_by(PullRequest.created_at.desc())
            .first()
        )
        owner = repo = branch = None
        if pr:
            try:
                owner, repo = pr.repo.split("/", 1)
                branch = pr.branch
            except Exception:
                owner = repo = branch = None
        if not branch:
            prev = db.query(PreviewDeployRow).filter(PreviewDeployRow.run_id == run_id).first()
            if prev:
                owner = prev.owner
                repo = prev.repo
                branch = prev.branch

        out: Dict[str, object] = {}
        # 2) Publish pending -> final
        state_map = {"ok": "success", "alerts": "failure"}
        desc = ("No alerts" if status == "ok" else f"{len(alerts)} alerts")
        if owner and repo and branch:
            pend = gh.set_alerts_status_for_branch(owner, repo, branch, state="pending", description="Alerts computing")
            fin = gh.set_alerts_status_for_branch(owner, repo, branch, state=state_map[status], description=desc)
            # upsert PR summary Ops section when PR coordinates exist
            try:
                run = db.get(RunDB, run_id)
                ops_md = self._build_ops_md(run=run, slo=slo, alerts=alerts)
                up_res = gh.upsert_pr_summary_comment_for_run_with_ops(db, run_id, ops_md)
            except Exception:
                up_res = {"error": "upsert failed"}
            out["pending"] = pend
            out["final"] = fin
            out["comment"] = up_res
            if isinstance(pend, dict) and (pend.get("dry_run") or pend.get("skipped")):
                out["dry_run"] = True
                out["status"] = {"context": gh.CTX_ALERTS, "state": state_map[status]}
                try:
                    out["summary"] = self._build_ops_md(run=db.get(RunDB, run_id), slo=slo, alerts=alerts)
                except Exception:
                    pass
        else:
            # No branch coordinates available; still return generated summary for API consumers/tests
            out["dry_run"] = True
            out["status"] = {"context": gh.CTX_ALERTS, "state": state_map[status]}
            try:
                out["summary"] = self._build_ops_md(run=db.get(RunDB, run_id), slo=slo, alerts=alerts)
            except Exception:
                pass
        return out


