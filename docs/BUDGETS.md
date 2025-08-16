### Budgets (Phase 19)

- Deterministic, local-only accounting: no external billing APIs.
- Defaults:
  - `BUDGET_ENABLED=1`
  - `BUDGET_USD_PER_1K_TOKENS=0.01`
  - `BUDGET_WARN_PCT=0.8`
  - `BUDGET_BLOCK_PCT=1.0`
  - `BUDGET_RUN_USD=0.01` (example cap; override as needed)
  - `BUDGET_PERSONAS` or `BUDGET_PERSONA_LIMITS` (JSON) optional.
- Status: `ai-csuite/budget` (optional) follows pending → success/failure. Dry‑run simulated when `GITHUB_WRITE_ENABLED=0`.
- Endpoints:
  - `POST /integrations/budget/{run_id}/compute`
  - `GET /integrations/budget/{run_id}`
  - `POST /integrations/budget/{run_id}/reset`
- Ledger table: `budget_usages` with unique `(run_id, persona)`; persona `NULL` row stores totals.


