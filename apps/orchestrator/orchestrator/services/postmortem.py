from __future__ import annotations

import os
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import RunDB
from ..security import mask_dict, apply_redaction
from ..kb import ingest_text
from ..ai_graph.repo import get_history as repo_get_history
from .alerts import AlertsService
from .budget import BudgetService


# In-memory, per-process store (Phase 30 requirement: no DB changes)
_ARTIFACTS: Dict[str, Dict[str, Any]] = {}
_KB_INGESTED: Dict[str, bool] = {}


def _env_true(key: str, default: str = "1") -> bool:
    try:
        v = os.getenv(key, default).strip().lower()
    except Exception:
        v = default
    return v not in {"0", "false", "no"}


def _env_list(key: str) -> List[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _aggregate_retries(history: List[Dict[str, Any]]) -> Tuple[int, Optional[str]]:
    # Group by step_index to compute retries and failed_step
    by_idx: Dict[int, List[Dict[str, Any]]] = {}
    for h in history:
        by_idx.setdefault(int(h["step_index"]), []).append(h)
    retries_total = 0
    failed_step: Optional[str] = None
    # Highest step_index with terminal error wins as failed_step
    max_err_idx: Optional[int] = None
    for idx, items in by_idx.items():
        items.sort(key=lambda r: int(r["attempt"]))
        max_attempt = int(items[-1]["attempt"]) if items else 0
        if max_attempt > 1:
            retries_total += (max_attempt - 1)
        last_status = str(items[-1]["status"]) if items else "ok"
        if last_status == "error":
            if max_err_idx is None or idx > max_err_idx:
                max_err_idx = idx
                failed_step = str(items[-1]["step_name"]) if items else None
    return retries_total, failed_step


def _alerts_summary(db: Session, run_id: str) -> Dict[str, Any]:
    svc = AlertsService()
    try:
        snap = svc.get_snapshot(db, run_id)
    except Exception:
        return {"status": "n/a", "counts": {"by_type": {}, "by_severity": {}, "total": 0}}
    by_type: Dict[str, int] = {}
    by_sev: Dict[str, int] = {}
    total = 0
    for a in (snap.get("alerts") or []):
        t = str(a.get("type") or "")
        s = str(a.get("severity") or "")
        if t:
            by_type[t] = by_type.get(t, 0) + 1
        if s:
            by_sev[s] = by_sev.get(s, 0) + 1
        total += 1
    return {"status": snap.get("status", "ok"), "counts": {"by_type": by_type, "by_severity": by_sev, "total": total}}


def _budget_summary(db: Session, run_id: str) -> Dict[str, Any]:
    svc = BudgetService()
    try:
        b = svc.get(db, run_id)
        totals = b.get("totals") or {}
        return {
            "status": b.get("status", "ok"),
            "totals": {
                "cost_cents": int(totals.get("cost_cents") or 0),
                "budget_cents": int(totals.get("budget_cents") or 0),
                "pct_used": float(totals.get("pct_used") or 0.0),
            },
        }
    except Exception:
        return {"status": "n/a", "totals": {"cost_cents": 0, "budget_cents": 0, "pct_used": 0.0}}


def _gating_can_merge_and_not_green(db: Session, run_id: str) -> Tuple[Optional[bool], List[str]]:
    try:
        svc = AlertsService()
        info = svc._compute_pr_gating_state(db, run_id)  # type: ignore[attr-defined]
        if not info:
            return None, []
        return bool(info.get("all_green")), list(info.get("not_green") or [])
    except Exception:
        return None, []


def _derive_causes(history: List[Dict[str, Any]], *, not_green: List[str]) -> List[str]:
    causes: List[str] = []
    # Retry exhaust when a step ends in error with >= 3 attempts
    by_idx: Dict[int, List[Dict[str, Any]]] = {}
    for h in history:
        by_idx.setdefault(int(h["step_index"]), []).append(h)
    for idx, items in by_idx.items():
        items.sort(key=lambda r: int(r["attempt"]))
        if not items:
            continue
        last = items[-1]
        if str(last.get("status")) == "error" and int(last.get("attempt") or 0) >= 3:
            causes.append("retry_exhaust")
            break
    if not_green:
        causes.append("gate_not_green:" + ",".join(sorted(set(not_green))))
    return causes


def _derive_learnings(budget_status: str, causes: List[str]) -> List[str]:
    tags: List[str] = []
    if any(c.startswith("retry_exhaust") for c in causes):
        tags.append("retry_exhaust")
    if budget_status == "warn":
        tags.append("budget_warn")
    if budget_status == "blocked":
        tags.append("budget_block")
    if any(c.startswith("gate_not_green") for c in causes):
        tags.append("gate_not_green")
    # Deterministic order
    return sorted(sorted(set(tags)))


def _build_summary_headline(run_id: str, meta: Dict[str, Any], alerts_sum: Dict[str, Any], budget_sum: Dict[str, Any]) -> str:
    alerts_count = int(((alerts_sum or {}).get("counts") or {}).get("total") or 0)
    budget_status = str((budget_sum or {}).get("status") or "n/a")
    failed = meta.get("failed_step") or "-"
    retries = int(meta.get("retries") or 0)
    return f"Run {run_id} · status={meta.get('status')} · failed={failed} · retries={retries} · alerts={alerts_count} · budget={budget_status}"


class PostmortemService:
    def _enabled(self) -> bool:
        return _env_true("POSTMORTEM_ENABLED", "1")

    def generate(self, db: Session, run_id: str) -> Dict[str, Any]:
        if not self._enabled():
            raise ValueError("postmortem disabled (POSTMORTEM_ENABLED=0)")
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")

        # Persisted history is the single source of truth
        history = repo_get_history(db, run_id)
        # Deterministic timeline entries
        timeline = [
            {
                "step": h["step_name"],
                "status": h["status"],
                "attempt": int(h["attempt"]),
                **({"error": h["error"]} if h.get("error") else {}),
            }
            for h in history
        ]

        # Attempts & retries
        total_attempts = len(history)
        retries_total, failed_step = _aggregate_retries(history)

        # Alerts & budget summaries
        alerts_sum = _alerts_summary(db, run_id)
        budget_sum = _budget_summary(db, run_id)

        # Gating (local-only; no network)
        can_merge, not_green = _gating_can_merge_and_not_green(db, run_id)

        # Causes and learnings
        causes = _derive_causes(history, not_green=not_green)
        learnings = _derive_learnings(str(budget_sum.get("status") or "n/a"), causes)

        # Tags: env defaults + learnings + base marker
        tags = ["postmortem"] + _env_list("POSTMORTEM_TAGS") + learnings
        tags = sorted(sorted(set([t for t in tags if t])))

        meta = {
            "run_id": run_id,
            "status": run.status,
            "total_attempts": total_attempts,
            "retries": retries_total,
            **({"failed_step": failed_step} if failed_step else {}),
            **({"can_merge": can_merge} if can_merge is not None else {}),
        }

        artifact: Dict[str, Any] = {
            "meta": meta,
            "timeline": timeline,
            "alerts": alerts_sum,
            "budget": budget_sum,
            "causes": causes,
            "actions": self._build_actions(failed_step=failed_step, not_green=not_green),
            "learnings": learnings,
            "tags": tags,
        }

        # Deterministic headline retained for search/results
        headline = _build_summary_headline(run_id, meta, alerts_sum, budget_sum)

        # Persist in memory (idempotent)
        _ARTIFACTS[run_id] = artifact

        # Derived metrics
        duration_total_ms = sum(int(h.get("duration_ms") or 0) for h in history)
        metrics = {
            "attempts_total": total_attempts,
            "retries_total": retries_total,
            "alerts_count": int(((alerts_sum or {}).get("counts") or {}).get("total") or 0),
            "duration_total_ms": duration_total_ms,
            "headline": headline,
        }

        # Optional auto-ingest to KB
        if _env_true("POSTMORTEM_AUTO_KB", "0"):
            try:
                _ = self.ingest_kb(db, run_id)
            except Exception:
                pass

        return {"artifact": artifact, "metrics": metrics}

    def _build_actions(self, *, failed_step: Optional[str], not_green: List[str]) -> List[Dict[str, str]]:
        actions: List[Dict[str, str]] = []
        if failed_step:
            actions.append({"id": "PM-A1", "desc": f"Add test for {failed_step}", "owner": "QA", "priority": "high"})
        if not_green:
            actions.append({"id": "PM-A2", "desc": "Re-evaluate DoR/gates", "owner": "CoS", "priority": "medium"})
        return actions

    def get(self, run_id: str) -> Dict[str, Any]:
        if run_id not in _ARTIFACTS:
            raise LookupError("postmortem not found")
        return _ARTIFACTS[run_id]

    def reset(self, run_id: str) -> Dict[str, Any]:
        existed = run_id in _ARTIFACTS
        if existed:
            _ARTIFACTS.pop(run_id, None)
        _KB_INGESTED.pop(run_id, None)
        return {"deleted": bool(existed)}

    def ingest_kb(self, db: Session, run_id: str) -> Dict[str, Any]:
        if not self._enabled():
            raise ValueError("postmortem disabled (POSTMORTEM_ENABLED=0)")
        art = _ARTIFACTS.get(run_id)
        if not art:
            raise LookupError("postmortem not found")
        # Look up run for tenant/project
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")
        # Build short, redacted paragraph
        meta = art.get("meta", {})
        alerts = art.get("alerts", {})
        budget = art.get("budget", {})
        alerts_count = int(((alerts or {}).get("counts") or {}).get("total") or 0)
        budget_status = str((budget or {}).get("status") or "n/a")
        failed = meta.get("failed_step") or "-"
        retries = int(meta.get("retries") or 0)
        text = (
            f"Postmortem for run {run_id}: status={meta.get('status')}, failed_step={failed}, "
            f"retries={retries}, alerts={alerts_count}, budget={budget_status}. "
            f"Tags={','.join(art.get('tags') or [])}."
        )
        safe_text = apply_redaction(text, mode="strict")

        # Idempotent by (tenant, project, kind, ref_id)
        from ..models import KbChunk
        exists = (
            db.query(KbChunk)
            .filter(KbChunk.tenant_id == run.tenant_id, KbChunk.project_id == run.project_id, KbChunk.kind == "postmortem", KbChunk.ref_id == run_id)
            .count()
        )
        if exists:
            _KB_INGESTED[run_id] = True
            return {"ok": True, "already": True, "chunks": int(exists)}

        chunks = ingest_text(db, tenant_id=run.tenant_id, project_id=run.project_id, kind="postmortem", ref_id=run_id, text=safe_text)
        _KB_INGESTED[run_id] = True
        return {"ok": True, "chunks": int(chunks)}

    def search(self, q: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        # Deterministic text/tags search over in-memory artifacts
        q_norm = (q or "").strip().lower()
        tag_norm = (tag or "").strip().lower()
        results: List[Tuple[str, Dict[str, Any]]] = []
        for rid, art in _ARTIFACTS.items():
            tags = [str(t).lower() for t in (art.get("tags") or [])]
            meta = art.get("meta", {})
            alerts = art.get("alerts", {})
            budget = art.get("budget", {})
            headline = _build_summary_headline(rid, meta, alerts, budget)
            text_blob = " ".join([
                rid,
                str(meta.get("status") or ""),
                " ".join(tags),
                headline,
            ]).lower()
            if tag_norm and tag_norm not in tags:
                continue
            if q_norm and q_norm not in text_blob:
                continue
            results.append((rid, {
                "run_id": rid,
                "tags": art.get("tags") or [],
                "status": meta.get("status"),
                "summary_headline": headline,
            }))
        # Stable ordering: run_id asc
        results.sort(key=lambda t: str(t[0]))
        return [r for _, r in results]


