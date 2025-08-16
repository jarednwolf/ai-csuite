from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import GraphState, BudgetUsage, PullRequest, RunDB
from ..integrations import github as gh


def _enabled() -> bool:
    try:
        v = os.getenv("BUDGET_ENABLED", "1").strip().lower()
    except Exception:
        v = "1"
    return v not in {"0", "false", "no"}


def _warn_pct(default: float = 0.8) -> float:
    try:
        return float(os.getenv("BUDGET_WARN_PCT", str(default)))
    except Exception:
        return default


def _block_pct(default: float = 1.0) -> float:
    try:
        return float(os.getenv("BUDGET_BLOCK_PCT", str(default)))
    except Exception:
        return default


def _rate_usd_per_1k(default: float = 0.01) -> float:
    try:
        return float(os.getenv("BUDGET_USD_PER_1K_TOKENS", str(default)))
    except Exception:
        return default


def _default_personas() -> List[str]:
    env = os.getenv("BUDGET_PERSONAS", "").strip()
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    return ["product", "design", "research", "cto", "engineer", "qa"]


def _persona_limits_usd() -> Dict[str, float]:
    raw = os.getenv("BUDGET_PERSONA_LIMITS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        out: Dict[str, float] = {}
        for k, v in (data.items() if isinstance(data, dict) else []):
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out
    except Exception:
        return {}


def _run_budget_usd(default: float = 0.01) -> float:
    # Optional override: run-level budget in USD
    try:
        return float(os.getenv("BUDGET_RUN_USD", str(default)))
    except Exception:
        return default


def _persona_for_step(step_name: str) -> Optional[str]:
    if step_name == "cto_plan":
        return "cto"
    if step_name in {"product", "design", "research", "engineer", "qa"}:
        return step_name
    # "release" or any other non-persona step maps to None
    return None


def _cost_cents_for_tokens(tokens: int, usd_per_1k: float) -> int:
    # cost_usd = tokens / 1000 * rate
    # Convert to cents and round to nearest int for determinism
    cents = (tokens * usd_per_1k * 100.0) / 1000.0
    # Floor to avoid over-counting fractional cents when near budget
    return int(math.floor(cents))


@dataclass
class BudgetThresholds:
    warn_pct: float
    block_pct: float


@dataclass
class RateModel:
    usd_per_1k_tokens: float


class BudgetService:
    TOKENS_PER_ATTEMPT_TOTAL = 100
    TOKENS_IN_FRACTION = 0.5  # split 50/50 in/out deterministically

    def compute(
        self,
        db: Session,
        run_id: str,
        *,
        warn_pct: Optional[float] = None,
        block_pct: Optional[float] = None,
        rate_usd_per_1k: Optional[float] = None,
        personas: Optional[List[str]] = None,
        run_budget_usd: Optional[float] = None,
        persona_budgets_usd: Optional[Dict[str, float]] = None,
    ) -> Dict:
        if not _enabled():
            raise ValueError("Budget is disabled (BUDGET_ENABLED=0)")

        # Validate run exists
        run = db.get(RunDB, run_id)
        if not run:
            raise LookupError("run not found")

        thresholds = BudgetThresholds(
            warn_pct=(warn_pct if warn_pct is not None else _warn_pct()),
            block_pct=(block_pct if block_pct is not None else _block_pct()),
        )
        rate = RateModel(usd_per_1k_tokens=(rate_usd_per_1k if rate_usd_per_1k is not None else _rate_usd_per_1k()))
        persona_list = personas if personas is not None else _default_personas()
        run_budget_usd_val = (run_budget_usd if run_budget_usd is not None else _run_budget_usd())
        run_budget_cents = int(round(run_budget_usd_val * 100.0))
        # Persona budgets in USD and cents
        persona_limits = dict(persona_budgets_usd or _persona_limits_usd())
        persona_budget_usd: Dict[str, float] = {}
        persona_budget_cents: Dict[str, int] = {}
        for p in persona_list:
            try:
                usd_val = float(persona_limits[p]) if p in persona_limits else run_budget_usd_val
            except Exception:
                usd_val = run_budget_usd_val
            persona_budget_usd[p] = usd_val
            persona_budget_cents[p] = int(round(usd_val * 100.0))

        # Aggregate tokens/costs from persisted graph history
        rows: List[GraphState] = (
            db.query(GraphState)
            .filter(GraphState.run_id == run_id)
            .order_by(GraphState.step_index.asc(), GraphState.attempt.asc())
            .all()
        )
        if not rows:
            # Allow computing even if graph hasn't run; totals are zero
            pass

        persona_totals: Dict[str, Dict[str, int]] = {p: {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0} for p in persona_list}
        totals = {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0}

        for r in rows:
            # Deterministic tokens per attempt
            t_total = self.TOKENS_PER_ATTEMPT_TOTAL
            t_in = int(math.floor(t_total * self.TOKENS_IN_FRACTION))
            t_out = t_total - t_in
            totals["tokens_in"] += t_in
            totals["tokens_out"] += t_out
            totals["tokens_total"] += t_total

            persona = _persona_for_step(r.step_name)
            if persona and persona in persona_totals:
                p = persona_totals[persona]
                p["tokens_in"] += t_in
                p["tokens_out"] += t_out
                p["tokens_total"] += t_total
        
        # Compute costs post-aggregation to preserve fractional cents
        totals_cost_cents = _cost_cents_for_tokens(totals["tokens_total"], rate.usd_per_1k_tokens)
        totals_cost_usd = (totals["tokens_total"] / 1000.0) * rate.usd_per_1k_tokens
        # enrich totals with cost
        totals_with_cost = dict(totals)
        totals_with_cost["cost_cents"] = totals_cost_cents

        # Evaluate thresholds
        pct_used = (totals_cost_usd / run_budget_usd_val) if run_budget_usd_val > 0 else 0.0
        if pct_used >= thresholds.block_pct:
            status = "blocked"
        elif pct_used >= thresholds.warn_pct:
            status = "warn"
        else:
            status = "ok"

        # Upsert ledger rows (idempotent)
        self._upsert_ledger(db, run_id, None, totals_with_cost, status)
        for persona in persona_list:
            p = persona_totals.get(persona, {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0})
            # Compute persona status vs persona budget (defaults to run budget when not specified)
            p_budget_usd = persona_budget_usd.get(persona, run_budget_usd_val)
            p_cost_usd = (p.get("tokens_total", 0) / 1000.0) * rate.usd_per_1k_tokens
            p_cost = _cost_cents_for_tokens(p.get("tokens_total", 0), rate.usd_per_1k_tokens)
            p_pct = (p_cost_usd / p_budget_usd) if p_budget_usd > 0 else 0.0
            if p_pct >= thresholds.block_pct:
                p_status = "blocked"
            elif p_pct >= thresholds.warn_pct:
                p_status = "warn"
            else:
                p_status = "ok"
            p_with_cost = dict(p)
            p_with_cost["cost_cents"] = p_cost
            self._upsert_ledger(db, run_id, persona, p_with_cost, p_status)

        # Build persona outputs (used for summary + GH comment)
        personas_out = []
        for persona in persona_list:
            p = persona_totals.get(persona, {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0})
            p_budget_usd = persona_budget_usd.get(persona, run_budget_usd_val)
            p_budget = persona_budget_cents.get(persona, run_budget_cents)
            p_cost = _cost_cents_for_tokens(p.get("tokens_total", 0), rate.usd_per_1k_tokens)
            p_cost_usd = (p.get("tokens_total", 0) / 1000.0) * rate.usd_per_1k_tokens
            p_pct = (p_cost_usd / p_budget_usd) if p_budget_usd > 0 else 0.0
            p_status = "ok"
            if p_pct >= thresholds.block_pct:
                p_status = "blocked"
            elif p_pct >= thresholds.warn_pct:
                p_status = "warn"
            personas_out.append({
                "persona": persona,
                "tokens_in": p["tokens_in"],
                "tokens_out": p["tokens_out"],
                "cost_cents": p_cost,
                "budget_cents": p_budget,
                "pct_used": round(p_pct, 4),
                "status": p_status,
            })
        
        # Publish GitHub status (pending -> final), and upsert summary comment with Budget section
        gh_result = self._publish_github(db, run_id, status=status, pct_used=pct_used, run_budget_cents=run_budget_cents, personas=personas_out)

        # Build response
        # attempts & updated_at from totals row
        tot_row = (
            db.query(BudgetUsage)
            .filter(BudgetUsage.run_id == run_id, BudgetUsage.persona == None)  # noqa: E711
            .first()
        )
        attempts = int(tot_row.attempts) if tot_row else 0
        updated_at = (tot_row.updated_at.isoformat() if (tot_row and tot_row.updated_at) else None)

        return {
            "run_id": run_id,
            "status": status,
            "thresholds": {"warn_pct": thresholds.warn_pct, "block_pct": thresholds.block_pct},
            "rate": {"usd_per_1k_tokens": rate.usd_per_1k_tokens},
            "totals": {
                "tokens_in": totals["tokens_in"],
                "tokens_out": totals["tokens_out"],
                "cost_cents": totals_cost_cents,
                "budget_cents": run_budget_cents,
                "pct_used": round(pct_used, 4),
            },
            "personas": personas_out,
            "attempts": attempts,
            "updated_at": updated_at,
            "gh": gh_result,
        }

    def _upsert_ledger(self, db: Session, run_id: str, persona: Optional[str], totals: Dict[str, int], status: str) -> None:
        row = (
            db.query(BudgetUsage)
            .filter(BudgetUsage.run_id == run_id, (BudgetUsage.persona == persona) if persona is not None else (BudgetUsage.persona == None))  # noqa: E711
            .first()
        )
        if row:
            row.tokens_in = int(totals.get("tokens_in", 0))
            row.tokens_out = int(totals.get("tokens_out", 0))
            row.cost_cents = int(totals.get("cost_cents", 0))
            row.status = status
            row.attempts = int(row.attempts or 0) + 1
            row.error = None
            db.commit()
        else:
            new_row = BudgetUsage(
                id=str(uuid.uuid4()),
                run_id=run_id,
                persona=persona,
                tokens_in=int(totals.get("tokens_in", 0)),
                tokens_out=int(totals.get("tokens_out", 0)),
                cost_cents=int(totals.get("cost_cents", 0)),
                status=status,
                attempts=1,
                error=None,
            )
            db.add(new_row)
            db.commit()

    def _publish_github(self, db: Session, run_id: str, *, status: str, pct_used: float, run_budget_cents: int, personas: List[Dict]) -> Dict:
        # Map status to GitHub state
        state = "success" if status in {"ok", "warn"} else "failure"
        percent = int(round(pct_used * 100.0))
        desc = f"Budget {percent}% of ${run_budget_cents/100:.2f}"

        # Find PR metadata
        pr: Optional[PullRequest] = (
            db.query(PullRequest)
            .filter(PullRequest.run_id == run_id)
            .order_by(PullRequest.created_at.desc())
            .first()
        )
        if not pr:
            return {"skipped": "no PR recorded for this run"}

        owner, repo = pr.repo.split("/", 1)
        # 1) Set pending at start, then final state
        pend = gh.set_budget_status_for_branch(owner, repo, pr.branch, state="pending", description="Budget computing")
        fin = gh.set_budget_status_for_branch(owner, repo, pr.branch, state=state, description=desc)

        # 2) Upsert summary comment with Budget section
        budget_md = self._build_budget_md(percent=percent, budget_cents=run_budget_cents, personas=personas)
        try:
            comment_res = gh.upsert_pr_summary_comment_for_run_with_budget(db, run_id, budget_md)
        except Exception as e:
            comment_res = {"error": str(e)}

        return {"pending": pend, "final": fin, "comment": comment_res}

    def _build_budget_md(self, *, percent: int, budget_cents: int, personas: List[Dict]) -> str:
        bar_full = min(max(percent, 0), 100)
        # Create a simple ASCII bar (20 chars)
        filled = int(round(bar_full / 5))  # 20 slots
        bar = "█" * filled + "░" * (20 - filled)
        lines = [
            "",
            "**Budget**",
            "",
            f"- Limit: ${budget_cents/100:.2f}",
            f"- Used: {percent}% {bar}",
        ]
        # Append persona overages
        over = [p for p in personas if p.get("status") in {"warn", "blocked"}]
        if over:
            lines.append("- Personas:")
            for p in over:
                pname = p.get("persona")
                ppct = int(round(float(p.get("pct_used") or 0.0) * 100.0))
                lines.append(f"  - {pname}: {ppct}%")
        return "\n".join(lines) + "\n"

    def get(self, db: Session, run_id: str) -> Dict:
        if not _enabled():
            raise ValueError("Budget is disabled (BUDGET_ENABLED=0)")
        rows: List[BudgetUsage] = (
            db.query(BudgetUsage)
            .filter(BudgetUsage.run_id == run_id)
            .all()
        )
        if not rows:
            raise LookupError("no budget records for this run")

        run_budget_cents = int(round(_run_budget_usd() * 100.0))
        thresholds = {"warn_pct": _warn_pct(), "block_pct": _block_pct()}

        personas: List[Dict] = []
        totals = None
        attempts = 0
        updated_at = None
        for r in rows:
            if r.persona is None:
                totals = {
                    "tokens_in": int(r.tokens_in or 0),
                    "tokens_out": int(r.tokens_out or 0),
                    "cost_cents": int(r.cost_cents or 0),
                    "budget_cents": run_budget_cents,
                    "pct_used": round((int(r.cost_cents or 0) / run_budget_cents) if run_budget_cents > 0 else 0.0, 4),
                    "status": r.status,
                }
                attempts = int(r.attempts or 0)
                updated_at = r.updated_at.isoformat() if r.updated_at else None
            else:
                personas.append({
                    "persona": r.persona,
                    "tokens_in": int(r.tokens_in or 0),
                    "tokens_out": int(r.tokens_out or 0),
                    "cost_cents": int(r.cost_cents or 0),
                    "status": r.status,
                })

        if not totals:
            raise LookupError("totals row missing for run")

        # Sort for stable output
        personas.sort(key=lambda x: x["persona"])  # type: ignore

        return {
            "run_id": run_id,
            "status": totals["status"],
            "thresholds": thresholds,
            "totals": totals,
            "personas": personas,
            "attempts": attempts,
            "updated_at": updated_at,
        }

    def reset(self, db: Session, run_id: str) -> Dict:
        # Idempotent reset for tests/demo
        _ = db.query(BudgetUsage).filter(BudgetUsage.run_id == run_id).delete()
        db.commit()
        return {"ok": True, "run_id": run_id}


