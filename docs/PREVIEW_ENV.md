### Budget CI Hook

To demonstrate budget computation and status publication locally/deterministically, use:

```bash
./scripts/preview_smoke_ci.sh <run_id>
```

This calls the budget compute endpoint with defaults and prints the JSON response. When `GITHUB_WRITE_ENABLED=0`, it simulates statuses/comments without writing to GitHub.

AI‑CSuite — Preview Environments (Phase 18)

Last updated: 2025‑08‑16

Scope

- Simulated, deterministic preview deployments per branch/PR.
- No external infra. All operations dry‑run when `GITHUB_WRITE_ENABLED=0`.
- Required status: `ai-csuite/preview-smoke` (pending → success/failure).

Env toggles

- `PREVIEW_ENABLED` (default 1): set 0/false/no to disable preview endpoints.
- `PREVIEW_BASE_URL` (default `http://preview.local`): base for composed preview URLs.
- `GITHUB_PR_ENABLED` and `GITHUB_WRITE_ENABLED` honored for statuses/comments.

API

- `POST /integrations/preview/{run_id}/deploy`
  - Body: `{ "owner": "...", "repo": "...", "branch": "feature/...", "base_url": "optional", "force": false }`
  - Action: upsert ledger record for `run_id`, set `ai-csuite/preview-smoke=pending` on branch (dry‑run simulated).
  - Response: `{ preview_url, status: "pending" }` (+ `github` details in dry‑run).

- `POST /integrations/preview/{run_id}/smoke`
  - Body: `{ "timeout_ms": 1000, "inject_fail": false }`
  - Action: deterministic smoke probe; updates status to success/failure; upserts a Preview section in PR summary (dry‑run simulated and returned).
  - Response: `{ ok, preview_url, status }` (+ `summary`, `statuses` in dry‑run).

- `GET /integrations/preview/{run_id}`
  - Response: `{ preview_url, status, attempts, updated_at }`.

Idempotency & Resume

- Table `preview_deploys` with unique constraint on `(run_id)` ensures idempotent upsert.
- `attempts` increments on each transition; status remains last terminal state until changed.

CI Hook

- Use `scripts/test_local.sh` which includes Phase 18 tests.
- Minimal example:

```bash
export GITHUB_WRITE_ENABLED=0
export GITHUB_PR_ENABLED=0
RUN_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/deploy -H 'content-type: application/json' -d '{"owner":"acme","repo":"demo","branch":"feature/x"}' | jq .
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/smoke -H 'content-type: application/json' -d '{}' | jq .
```


