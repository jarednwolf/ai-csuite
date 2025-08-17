# SELF_DEV_AUTOPILOT
_Last updated: 2025-08-17_

This document defines how AI‑CSuite agents work on **the platform itself** safely. It scopes autonomy, allowed change classes by milestone, escalation paths, and the gates that must be green before any self‑change is merged.

## Scope

- **In-scope:** Repo docs, checklists, tests, mock adapters, provider scaffolds, low‑risk code hygiene, blueprint additions, progressive delivery of small reversible features, performance/cost optimizations, vendor shadows/ramps, and incident recovery (revert/bisect).
- **Out-of-scope (until explicitly unlocked):** Security model changes, auth/SSO flows, DB schema migrations that mutate data, network perimeter/Secrets handling, and policy relaxations.

## Autonomy Levels

- **L0 (Propose‑only):** Agent creates artifacts and PRs, **no** execution without human approval.
- **L1 (Capped autonomy):** Agent may execute within **budget + safety caps**; blocked by guardrails (evals, smoke, policy).

_The orchestrator enforces L0/L1 per run and per capability. Founder can override via Cockpit._

## Milestones → What agents can do

| Milestone | Phases | What’s Allowed | Gates (must be green) |
|---|---|---|---|
| **M1** | 49 | Docs/checklists only | `ai-csuite/self-docs`, Markdown lint, link check |
| **M2** | 47–53 | Test synthesis; mechanical code fixes; adapter scaffolds (mock/conformance) | All M1 + `ai-csuite/self-review`, preview smoke, eval baseline unchanged |
| **M3** | 57–58 | Small, reversible features **behind flags** with **canary** & **eval gates** | `ai-csuite/preview-smoke`, `ai-csuite/evals`, flag rollout policy |
| **M4** | 59–61 | Cost/perf tuning; vendor shadow→ramp autonomously within caps | Budget guard (`ai-csuite/budget`), shadow diff OK, no SLO/ROAS regression |

## Milestone M4 Endpoints & Artifacts

- Optimizer: `POST /self/optimize` → `apps/orchestrator/orchestrator/self/optimizer_report.json`
- Incidents: `POST /incidents/revert`, `POST /incidents/bisect` → `apps/orchestrator/orchestrator/incidents/*.json`
- Vendor Swap: `/providers/shadow/start`, `/providers/shadow/compare-once`, `/providers/ramp/{stage}` → `apps/orchestrator/orchestrator/self/vendor_shadow_report.json`

## Allowed Change Classes (by milestone)

- **M1:** `docs/**`, `*.md`, `scripts/*.sh` (help text only), `apps/orchestrator/tests/**` (new tests allowed; no test deletions).
- **M2:**
  - **Mechanical:** format/lint/type‑hint fixes, dead‑code removal, comment/docstrings; **no logic changes**.
  - **Test Synthesis:** add tests for uncovered modules; may refactor tests; **no runtime changes required**.
  - **Provider Scaffolds:** new adapter skeletons passing conformance, **shadow disabled in CI**.
- **M3:** Small features behind flags; guarded rollout with canary (5→25→50→100); require preview env + evals ≥ baseline.
- **M4:** Performance/cost improvements (caching, async, model routing) with stable outputs; vendor shadows/ramps under Budget Governor.

## Escalation Paths

Escalate to **Founder** (via CoS) if any of:
- One‑way door (non‑reversible) or data‑destructive change.
- Expected effort ↑ > 20% vs. TechPlan.
- Security/PII/PHI exposure risk, or policy relax requested.
- Budget overrun > 100% or anomalous CPA/ROAS spike.
- Failing gates after max retries.

Escalate to **CTO** for: interface/contract changes, DB migrations, policy changes, or provider interface edits.

## Required PR Statuses (aggregated)

- **Core:** `ai-csuite/dor`, `ai-csuite/artifacts`, `ai-csuite/human-approval` (when L0), `ai-csuite/preview-smoke`, `ai-csuite/budget`.
- **Self‑work:** `ai-csuite/self-docs`, `ai-csuite/self-review`, `ai-csuite/self-lowrisk` (when applicable).
- **Quality:** `ai-csuite/evals` (Phase 40), tests=green, policy=green.

## Kill‑Switches

- Per‑capability kill (Lifecycle/Ads/Experiments/Providers).
- Global “Pause Self‑Work” flag.
- Auto‑pause on anomaly (latency p95 ↑ > 30%, eval score ↓ beyond threshold, or CPA/ROAS breach).

## PR Template (self‑work)
Title: [SELF] <short change description>
Summary: What changed and why (2–4 bullets).
Scope: Files/paths touched (glob).
Risk Tier: from CHANGE_RISK_MATRIX.json
Reversibility: Yes/No (explain)
Gates: list statuses expected
Speculative Report: link to self/spec_report.json (if Phase 51)
ADR: link (if Phase 52)


## Determinism

- All generated files sorted by keys; newline‑terminated; stable IDs/hashes.
- Seed RNG for any stochastic step; record seed in artifact.
