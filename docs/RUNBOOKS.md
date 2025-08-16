### Runbooks — Operations (Phase 20)

These runbooks describe local, deterministic remedies for common alerts. All steps avoid external dependencies and respect env toggles.

- Retry Exhausted (type: `retry_exhaust`)
  - Identify the step: from alert key `stepIndex:stepName`.
  - Inspect history: GET `/runs/{run_id}/graph/history` to confirm attempts and last error.
  - Remediate: POST `/runs/{run_id}/graph/resume` with `inject_failures` cleared to let the graph continue, or re-run start with different controls.
  - Verify: POST `/integrations/alerts/{run_id}/compute` — alert clears when the step succeeds.

- PR Gating Stuck (type: `pr_gating_stuck`)
  - Confirm contexts not green: GET `/integrations/github/pr/{run_id}/statuses`.
  - If preview is pending, run Phase 18: `/integrations/preview/{run_id}/deploy` then `/integrations/preview/{run_id}/smoke`.
  - If DoR failing, run `/integrations/github/pr/{run_id}/refresh-status` after fixing discovery.
  - Verify: recompute alerts; clears once required contexts are green or gating disabled.

- SLO Burn (type: `slo_burn`)
  - Check recent error attempts: GET `/runs/{run_id}/graph/history` and `/runs/{run_id}/metrics`.
  - Remediate: reduce injected failures, resume run, or raise thresholds temporarily in compute body for triage.
  - Verify: recompute with standard thresholds; clears when error ratio drops below burn threshold.

- Budget Overflow (type: `budget_overflow`)
  - Inspect budget: GET `/integrations/budget/{run_id}`.
  - Remediate: recompute budget with higher thresholds or reduce persona loops.
  - Verify: recompute alerts; clears when budget ledger status is not `blocked`.

Notes
- Respect dry‑run: with `GITHUB_WRITE_ENABLED=0`, statuses and comments are simulated and returned in responses; ledgers are still updated locally.
- Idempotent: recomputing alerts updates existing rows (no duplicates).


