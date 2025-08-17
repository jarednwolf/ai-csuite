# Experiment Policy
AI‑CSuite Experiment Policy (Phase 35)

This policy governs feature flags, A/B tests, and bandit strategies.

Policy file

- Example: `apps/orchestrator/orchestrator/experiments/policy.json` (real path can be overridden in production).

Supported modes

- Flags: deterministic on/off set via provider.
- A/B: pass `variants` weights; the system selects the argmax deterministically.
- Bandits: mock MAB adds infinitesimal noise to break ties; contextual hook uses request context deterministically.

Endpoints

- POST `/experiments/start` with `{ experiment_id, plan, seed }` → returns chosen arm and a persisted state id.
- GET `/experiments/{id}/report` → returns a deterministic report stub including winner and policy used.
- POST `/flags/ramp` with `{ key, stage }` where stage ∈ {5,25,50,100}.

Determinism & Safety

- A seeded RNG is used to ensure fully repeatable test outcomes.
- Stopping rules and MDE calculators are read from policy and surfaced in reports.
- Allowed designs: AB, MAB (Thompson/BayesUCB), Contextual Bandit (optional)
- Stopping rules: power-based or Bayesian credible interval
- MDE calculator: binomial and continuous metrics
- Guardrails: loss caps, max exposure, sequential testing controls
- Promotion: flag ramp 0→5→25→50→100% upon pass; auto-rollback rules

LLM Evals & Observability (Cross‑Link: Phases 24, 40)

- Offline eval harness produces `eval/report.json` and `eval/history.json` deterministically.
- Threshold gating is enforced via `scripts/eval_check.sh` in CI.
- API endpoints for orchestrator integration:
  - POST `/evals/run` — triggers eval harness; persists latest report and a trace row.
  - GET `/evals/report` — returns latest report for gating and dashboards.
- Observability provider: `LLMObservabilityProvider` records trace IDs with runs and evals for latency/cost/error attribution.
