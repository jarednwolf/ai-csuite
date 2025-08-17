1) Comprehensive handoff document (commit this)

Save as: docs/AI-CSUITE_HANDOFF.md

# AI‑CSuite — Handoff & Bootstrap (v0.11)
_Last updated: 2025‑08‑15_

This document captures the state of the **AI‑CSuite** orchestrator, how to stand it up locally, how PR flows and webhooks work, what tests exist (local + live), and how to continue toward an autonomous, multi‑agent AI C‑suite with LangGraph/Temporal.

---

## 0) TL;DR (copy/paste to get going)

```bash
# Ensure Python 3.12.5 (pyenv) then rebuild venv & install deps
./scripts/rebuild_env.sh

# Doctor check: docker, API health, env, GitHub token
./scripts/dev_doctor.sh

# Run the local integration tests (Phases 3–11 + webhook sim)
./scripts/test_local.sh
```

If you plan to use GitHub live PRs from the orchestrator, set:

export GITHUB_TOKEN=<PAT with repo + workflow>
export E2E_REPO_OWNER=jarednwolf
export E2E_REPO_NAME=ai-csuite
export ORCH_BASE=http://localhost:8000
pytest -m requires_github -q

1) Architecture Snapshot

Services

orchestrator (FastAPI / Uvicorn)
Path: apps/orchestrator/orchestrator/

Core domain: Projects, Roadmap Items, Runs

Knowledge base (simple text chunks)

Discovery / DoR checks generating PRD + Design notes + Research summary

GitHub integration (open PR, post statuses, approvals, merge, PR summary comment)

Webhooks endpoint (with smee support for local dev)

LangGraph mini‑pipeline with in‑memory state, endpoints to start/check

Postgres (pgvector image)
Path: db/schema.sql for bootstrap tables

Redis for caches / state

Docker Compose to run the stack locally

Key Features by Phase

Phase 1–3: API skeleton, Runs resource

Phase 4: Discovery/DoR and PRD/design/research artifacts

Phase 5: Knowledge base ingest/search and references into PRD

Phase 6: GitHub PR create (branch per roadmap item)

Phase 7: Required GitHub PR statuses (ai-csuite/dor, ai-csuite/human-approval, ai-csuite/artifacts) + approve/merge endpoints

Phase 8: Webhooks (push/pull_request) with smee local tunnel

Phase 9: PR summary comment upsert (marker‑based), dry‑run support

Phase 10: LangGraph pipeline + /runs/{id}/graph/start and /state endpoints
Phase 11: Postgres‑persisted graph state, /graph/history, /graph/resume with pause semantics
Phase 31–33: Provider Abstraction Layer (PAL), Conformance, Shadow & Ramp
Phase 54: Provider Adapter Scaffold → Conformance report (`POST /self/providers/scaffold`)
Phase 55: Supply‑Chain Upgrader (offline; proposal artifact)
Phase 56: Blueprint Library Auto‑Expansion (`POST /self/blueprints/scaffold`)

2) Environment & Tooling

Languages & Versions

Python: 3.12.5 (pin this everywhere; 3.13 causes NumPy build failures)

Docker Desktop on macOS (arm64)

Postgres: pgvector/pgvector:pg15

Redis: redis:7-alpine

Python Setup

scripts/rebuild_env.sh — ensures pyenv local 3.12.5, rebuilds .venv, installs runtime + dev deps.

scripts/dev_env_check.sh — validates Python version, patches Dockerfile & GH workflows to 3.12.5, imports NumPy, runs pytest.

Core Runtime Requirements (excerpt from apps/orchestrator/requirements.txt)

fastapi, uvicorn[standard], pydantic

httpx, SQLAlchemy, psycopg[binary], python-dotenv

numpy==2.0.1 (works with Python 3.12.x)

temporalio==1.7.0 (future phases)

LangGraph: langgraph==0.2.32, langchain-core==0.2.32

3) Secrets & Environment Variables

Create .env (local only; never commit secrets):

# Orchestrator
AUTO_ENSURE_DISCOVERY=1

# GitHub
GITHUB_TOKEN=ghp_***           # PAT with repo + workflow scope
GITHUB_PR_ENABLED=1            # 0 to disable PR creation
GITHUB_WRITE_ENABLED=1         # 0 yields dry-run (no writes)

# Webhooks
WEBHOOK_SECRET=<random-hex>
SMEE_URL=<your smee channel url>   # optional; for local only

# DB (docker-compose sets defaults; override if needed)
POSTGRES_USER=csuite
POSTGRES_PASSWORD=csuite
POSTGRES_DB=csuite

# Redis (default from compose)
REDIS_URL=redis://redis:6379/0

4) Running Locally
# Build & start services
docker compose up --build -d

# Health check
curl http://localhost:8000/healthz   # {"ok": true}


Create project + roadmap item + run

PROJECT=$(curl -s -X POST http://localhost:8000/projects \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"Demo","description":"","repo_url":"https://github.com/jarednwolf/ai-csuite.git"}')

PROJECT_ID=$(echo "$PROJECT" | jq -r .id)

ITEM=$(curl -s -X POST http://localhost:8000/roadmap-items \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"New Feature"}')

ITEM_ID=$(echo "$ITEM" | jq -r .id)

# Ensure Discovery / DoR artifacts
curl -s -X POST "http://localhost:8000/roadmap-items/$ITEM_ID/discovery/ensure" | jq .

# Create & start a run (will open a PR if enabled and token present)
RUN=$(curl -s -X POST http://localhost:8000/runs \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}')

RUN_ID=$(echo "$RUN" | jq -r .id)
curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | jq .


LangGraph endpoints

curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start | jq .
curl -s http://localhost:8000/runs/$RUN_ID/graph/state | jq .
# Early stop / resume demo:
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start \
  -H 'content-type: application/json' -d '{"stop_after":"research"}' | jq .
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/resume -d '{}' | jq .

UI

- Open `http://localhost:8000/ui` for the Founder Cockpit.
- Create from Blueprint: open `http://localhost:8000/ui/blueprints` to list blueprints (sorted) and scaffold deterministically via existing API. In dry‑run (`GITHUB_WRITE_ENABLED=0`), owner/name can be omitted for a safe simulation.
- Per‑run view: `http://localhost:8000/ui/run/$RUN_ID` shows:
  - Run status and created_at
  - PR statuses summary (from `/integrations/github/pr/{run_id}/statuses`)
  - Timeline (from `/runs/{run_id}/graph/history`)
  - Metrics (from `/runs/{run_id}/metrics`)
  - Approve and Merge buttons that call existing endpoints
  - Budget tile reads `/integrations/budget/{run_id}` and includes a "Compute Budget" action that POSTs `/integrations/budget/{run_id}/compute` with deterministic defaults (`warn_pct=0.8`, `block_pct=1.0`, `usd_per_1k_tokens=0.01`).
- Dry‑run gating: when `GITHUB_WRITE_ENABLED=0`, the UI shows a banner and disables write actions. A local-only override for tests: append `?dry_run=1` to the run page URL.

Postmortems (Phase 30)

- Deterministic, offline postmortem generation and KB ingest.
- Endpoints:
  - `GET /postmortems/{run_id}` — returns artifact if generated; 404 otherwise
  - `POST /postmortems/{run_id}/generate` — compute and persist artifact (idempotent)
  - `POST /postmortems/{run_id}/reset` — clear persisted artifact and counters for tests
  - `POST /postmortems/{run_id}/ingest-kb` — ingest a redacted summary paragraph into KB; idempotent
  - `GET /postmortems/search?q=...&tag?=...` — deterministic search over artifacts
- Cockpit: `http://localhost:8000/ui/postmortems` lists artifacts sorted by `run_id` asc with controls:
  - Refresh
  - Generate (run_id)
  - Ingest to KB (run_id)
- Env toggles (default deterministic behavior):
  - `POSTMORTEM_ENABLED=1` (disable with 0)
  - `POSTMORTEM_AUTO_KB=0` (when 1, generation also ingests the redacted summary)
  - `POSTMORTEM_TAGS=` (optional comma-separated default tags)

Integrations (Phase 29)

- Deterministic, offline partner framework with adapters, rate limits, retries, circuit breaker, and idempotency.
- Endpoints:
  - `GET /integrations/partners` — list registered adapters with policy, counters, and state.
  - `POST /integrations/partners/{partner_id}/call` — invoke op with `{op, payload?, idempotency_key?}`; enforces idempotency, rate-limit, retry/backoff (tracked), circuit breaker; returns `{status, result?, retried, backoff_ms, rate_remaining, circuit_state}`; 400 on rate-limited/open-circuit/failure.
  - `GET|PATCH /integrations/partners/{partner_id}/policy` — read/update deterministic policy for the process.
  - `GET /integrations/partners/{partner_id}/stats` — counters `{calls, retries, rate_limited, deduped, failures, circuit_open}`; `POST /integrations/partners/{id}/reset` clears state/counters.
  - `POST /integrations/partners/tick` — deterministic time tick; refills tokens to `rate_limit` for all adapters.
- Built‑in mock adapter `mock_echo`:
  - Ops: `echo` (returns payload), `fail_n_times` (fails N attempts for a single call id, then succeeds) for retry/circuit tests.
- Cockpit page: `http://localhost:8000/ui/integrations` lists partners (sorted) and provides Tick + Call controls.
- Environment toggles (read at startup; PATCH overrides persist for process lifetime):
  - `PARTNER_ENABLED=1` (default on)
  - `PARTNER_RATE_LIMIT=60`
  - `PARTNER_RETRY_MAX=3`
  - `PARTNER_BACKOFF_MS=0` (tracked, not slept)
  - `PARTNER_CIRCUIT_THRESHOLD=5`
  - `PARTNER_WINDOW_TOKENS=60`

Scheduler (Phase 28)

- Deterministic, offline-only scheduler with priorities, quotas, and simple concurrency.
- Endpoints:
  - `POST /scheduler/enqueue` — enqueue `{run_id, priority?}` (idempotent). Returns 400 when backpressure (`queue_max`) exceeded.
  - `GET /scheduler/queue` — snapshot: counts and deterministically sorted queued items (priority desc, then enqueued_at asc, then run_id asc).
  - `POST /scheduler/step` — lease next eligible run respecting global and per-tenant concurrency; synchronously starts the run; returns updated snapshot and `leased` id.
  - `GET /scheduler/policy` and `PATCH /scheduler/policy` — read/update policy for `global_concurrency`, `tenant_max_active`, `queue_max`, `enabled`.
  - `GET /scheduler/stats` — counters: `leases`, `skipped_due_to_quota`, `completed`.
- Cockpit: `GET /ui/scheduler` — table view of queue (sorted), policy/stats tiles, and a Step button that calls `/scheduler/step`.
- Env toggles (read at startup; can be overridden via PATCH for the process):
  - `SCHED_ENABLED=1`
  - `SCHED_CONCURRENCY=2`
  - `SCHED_TENANT_MAX_ACTIVE=1`
  - `SCHED_QUEUE_MAX=100`
- Determinism: no threads, no timers, no network calls; fairness is round‑robin across tenants for same priority.

5) GitHub Flow, Statuses, Webhooks, App Factory

PR statuses required

aI-csuite/dor — DoR passed

aI-csuite/human-approval — requires explicit human approval call

aI-csuite/artifacts — AI‑CSuite committed artifacts

Approve & merge (from orchestrator)

# Check statuses
curl -s http://localhost:8000/integrations/github/pr/$RUN_ID/statuses | jq .

# Approve
curl -s -X POST http://localhost:8000/integrations/github/pr/$RUN_ID/approve | jq .

# Merge (squash)
curl -s -X POST "http://localhost:8000/integrations/github/pr/$RUN_ID/merge?method=squash" | jq .


PR summary comment

Marker prefix: internal constant (ensures upsert vs duplicate)

Manual refresh:

curl -s -X POST http://localhost:8000/integrations/github/pr/$RUN_ID/comment/refresh | jq .


Webhooks (local via smee)

Create a smee channel: npx smee-client --url https://smee.io/<channel> --target http://localhost:8000/webhooks/github

Set SMEE_URL in .env

On your repo: Settings → Webhooks

Payload URL: your smee channel URL

Content type: application/json

Secret: WEBHOOK_SECRET

Events: Push, Pull request

Trigger by pushing to the feature branch or opening a PR.

App Factory (Phase 17)

- Blueprints endpoints:
  - `GET /blueprints`
  - `GET /blueprints/{id}`
- Scaffolder endpoint:
  - `POST /app-factory/scaffold`

Example (dry‑run):

```bash
export GITHUB_WRITE_ENABLED=0
curl -s http://localhost:8000/blueprints | jq .
curl -s http://localhost:8000/blueprints/web-crud-fastapi-postgres-react | jq .
curl -s -X POST http://localhost:8000/app-factory/scaffold \
  -H 'content-type: application/json' \
  -d '{
    "blueprint_id": "web-crud-fastapi-postgres-react",
    "target": {"mode": "existing_repo", "owner": "'$E2E_REPO_OWNER'", "name": "'$E2E_REPO_NAME'", "default_branch": "main"},
    "run_id": "op-demo"
  }' | jq .
```

Blueprint Library & Quality Gates (Phase 26)

- Manifests live under `blueprints/*.json` and follow `orchestrator.blueprints.models.BlueprintManifest`.
- New curated manifests:
  - `blueprints/mobile-crud-expo-supabase.json`
  - `blueprints/realtime-media-web.json`
- Deterministic validator/report:
  - Script: `scripts/blueprints_report.py` → writes `blueprints/report.json` with stable keys, sorted lists, newline termination.
  - Wrapper: `scripts/blueprints_check.sh` exits non‑zero on manifest errors or gating violations.
  - Offline only; no network calls; timestamps reuse on identical reruns.

Quickstart:

```bash
# Validate and generate report
python3 scripts/blueprints_report.py
cat blueprints/report.json | jq .

# CI‑like wrapper
bash scripts/blueprints_check.sh
```

Environment toggles:

- `BLUEPRINTS_ENABLED=1` (0 disables)
- `BLUEPRINTS_OUTDIR=blueprints` (output dir for report)
- `BLUEPRINTS_INCLUDE` / `BLUEPRINTS_EXCLUDE` (comma‑sep ids or globs)
- `BLUEPRINTS_ALLOW_WARN_OVERRIDE=0` (reserved)
- `BLUEPRINTS_WRITE_KB=0` (1 ingests redacted summary rows to local KB)

6) Tests & Scripts

Local (safe)

./scripts/test_local.sh
./scripts/supply_chain_check.sh   # Phase 21: lockfiles, SBOM, licenses, pins
# runs: health, phases 3–5, 9–11, webhook simulation (dry-run)


Live GitHub (creates real PRs)

export GITHUB_TOKEN=<PAT>
export E2E_REPO_OWNER=jarednwolf
export E2E_REPO_NAME=ai-csuite
export ORCH_BASE=http://localhost:8000
pytest -m requires_github -q


6.1) Preview Environments (Phase 18)

Preview deployments are simulated locally and gated by envs. No external infra is required in this phase.

Dry‑run example:

```bash
export GITHUB_WRITE_ENABLED=0
export GITHUB_PR_ENABLED=0
export PREVIEW_ENABLED=1
export PREVIEW_BASE_URL=http://preview.local

RUN_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/deploy -H 'content-type: application/json' -d '{"owner":"acme","repo":"demo","branch":"feature/my-change"}' | jq .
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/smoke -H 'content-type: application/json' -d '{"timeout_ms": 1000}' | jq .
curl -s http://localhost:8000/integrations/preview/$RUN_ID | jq .
```

Failure injection and resume:

```bash
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/smoke -H 'content-type: application/json' -d '{"inject_fail": true}' | jq .
curl -s -X POST http://localhost:8000/integrations/preview/$RUN_ID/smoke -H 'content-type: application/json' -d '{}' | jq .
```

Examples (individual tests)

pytest apps/orchestrator/tests/test_phase7_statuses_merge.py -q
pytest apps/orchestrator/tests/test_phase10_graph_happy_path.py -q


CI

.github/workflows/ci.yml — local E2E + webhook sim with dry‑run

.github/workflows/live-e2e.yml — manual, requires secrets to talk to GH

6.2) Supply Chain & Build Integrity (Phase 21)

Deterministic, local-only checks and artifacts:

- Lockfiles: `scripts/gen_lockfiles.py` generates `apps/orchestrator/requirements.lock.txt` and `requirements-dev.lock.txt` from pinned inputs.
- SBOM: `scripts/sbom_gen.py` writes `sbom/orchestrator-packages.json` with stable ordering.
- Licenses: `scripts/license_check.py` writes `sbom/licenses.json`; exits non-zero on disallowed or unknown licenses (configurable).
- All-in-one: `scripts/supply_chain_check.sh` verifies Dockerfile base image pinning and Python version alignment, then runs lockfile + SBOM + license checks.

Environment toggles:

- `SUPPLY_CHAIN_ENABLED=1` (default) — set `0` to disable.
- `PYTHON_VERSION_PIN=3.12.5` (default) — checked against Dockerfiles and `.python-version`.
- `LICENSE_ALLOWLIST` — comma-separated allowlist; default includes MIT, BSD-2/3, Apache-2.0, ISC, PSF, MPL-2.0.
- `SUPPLY_CHAIN_ALLOW_UNKNOWN=0` — set `1` to allow unknown licenses.

6.3) Policy-as-Code Governance (Phase 22)

Local-only, deterministic merge gates enforced via a JSON policy bundle and scripts.

- Policy bundle: `policies/merge_gates.json`
- Inputs (facts): `policy/facts.json` (generated), pulling from:
  - `sbom/licenses.json` (Phase 21)
  - `policy/statuses.json` (required contexts fixture)
  - `policy/budget_snapshot.json` (Phase 19 snapshot fixture)
  - `policy/dor.json` (presence flags for PRD/Design/Research/acceptance_criteria)
- Scripts:
  - `scripts/policy_input_collect.py` — normalize inputs → `policy/facts.json`
  - `scripts/policy_eval.py` — evaluate bundle → `policy/report.json`
  - `scripts/policy_check.sh` — orchestrates collect + eval (non-zero on violations)
- Env:
  - `POLICY_ENABLED=1` (set `0` to disable)
  - `POLICY_INPUT` path to a prebuilt facts fixture (optional)
  - `POLICY_BUNDLE=policies/merge_gates.json` (override bundle path)
  - `POLICY_ALLOW_WARN_OVERRIDE=0` (set `1` to pass when only warnings exist)

Quickstart:

```bash
# Seed minimal local fixtures (example)
cat > policy/statuses.json <<'JSON'
{"statuses":[
 {"context":"ai-csuite/dor","state":"success"},
 {"context":"ai-csuite/human-approval","state":"success"},
 {"context":"ai-csuite/artifacts","state":"success"},
 {"context":"ai-csuite/preview-smoke","state":"success"}
]}
JSON
echo '{"status":"ok","totals":{"pct_used":0.2}}' > policy/budget_snapshot.json
echo '{"prd":true,"design":true,"research":true,"acceptance_criteria":true}' > policy/dor.json

# Run the policy check
POLICY_ENABLED=1 bash scripts/policy_check.sh

# Inspect outputs
cat policy/facts.json | jq .
cat policy/report.json | jq .
```

Sample violation message:

```
Policy violations (block)
 - [block] required_statuses_green: Required contexts missing or not green: ai-csuite/preview-smoke
```

## 6.4) Compliance Hardening (Phase 23)

Local-only, deterministic scans and audit logs.

- Secrets scanner:
  - Rules in `compliance/regexes.json` (ordered). Each rule: `id, category, severity, description, pattern, redaction`.
  - Run: `python3 scripts/secrets_scan.py` (respects `SECRETS_SCAN_INCLUDE`/`SECRETS_SCAN_EXCLUDE`).
  - Output: `compliance/secrets_report.json` (sorted keys, newline-terminated). Non-zero exit on any `severity: block` unless `COMPLIANCE_ALLOW_WARN_OVERRIDE=1`.

- Redaction filters:
  - Core helpers in `apps/orchestrator/orchestrator/security.py`: `apply_redaction(text, mode)` and `mask_dict(obj)`; modes: `strict` (default) and `relaxed`.
  - Vectors in `compliance/test_vectors.json`. Run: `python3 scripts/redaction_test_vectors.py` → `compliance/redaction_report.json`.

- Audit logging:
  - Append-only `audit_logs` table with minimal fields: `id, ts, actor, event_type, run_id, project_id, details_redacted JSON, request_id`.
  - Events emitted for: approvals, merges, preview deploy/smoke, budget compute/get/reset, webhook received (metadata only). Inputs redacted.
  - Toggle writes via `AUDIT_ENABLED=0`. Verify with `python3 scripts/audit_verify.py` → `compliance/audit_report.json`.

- One-shot wrapper:
  - `bash scripts/compliance_check.sh` runs secrets scan → redaction vectors → audit verify; obeys `COMPLIANCE_ENABLED` and other toggles.

## 6.5) Evaluation Harness (Phase 24)

Deterministic, offline evaluation of golden tasks.

- Scripts: `scripts/eval_run.py`, `scripts/eval_history.py`, `scripts/eval_check.sh`
- Golden suites: `eval/golden/*.json`
- Outputs: `eval/report.json`, `eval/history.json` (sorted keys, newline-terminated)

Quickstart:

```bash
export EVAL_ENABLED=1
export EVAL_OUTDIR=eval
python3 scripts/eval_run.py
python3 scripts/eval_history.py

# Threshold gating wrapper (default threshold 0.9)
bash scripts/eval_check.sh
```

Environment toggles:

- `EVAL_ENABLED` (default 1): 0 disables eval checks.
- `EVAL_INCLUDE` / `EVAL_EXCLUDE`: comma-separated globs for suites or `suite:task`.
- `EVAL_THRESHOLD` (default 0.9): per-suite minimum score.
- `EVAL_OUTDIR` (default `eval`): output directory.
- `EVAL_WRITE_KB` (default 0): 1 ingests redacted summary rows into local KB via `apps/orchestrator` helpers.
- `ORCH_BASE`: not required; harness uses in-process modules only.

Authoring golden tasks:

- Each suite JSON: `{id, version, threshold, tasks:[]}`. Each task: `{id, category, weight, asserts:[]}`.
- Deterministic assertion types only:
  - `file_json_eq` `{file, path, expect}`
  - `file_json_contains` `{file, path, expect_item}`
  - `function_contains` `{function, args, expect_sub}` (limited to stable helpers like `build_pr_summary_md`)
  - `echo_equals` `{text, expect}`
  - `redact_contains` `{text, mode, expect_sub}`
- No network calls; no randomness. Suites and tasks are sorted by `id`.

Reporting & history:

- `eval/report.json` includes per-suite stats and per-task status; timestamps are reused on idempotent reruns.
- `eval/history.json` appends/updates by content fingerprint; duplicates are suppressed for identical results.

## 6.6) IaC Provisioning & Progressive Delivery (Phase 25)

Deterministic, offline IaC simulation and rollout gating. No external cloud calls.

Artifacts and data:
- IaC modules: `iac/modules/*.json` (e.g., `core.json` with `api`, `worker`, `db` pins)
- Environments: `iac/environments/{staging,prod}.json`
- Plan/apply outputs: `iac/plan.json`, `iac/state.json`
- Rollout fixtures: `deployments/fixtures/canary_ok.json`, `deployments/fixtures/canary_bad.json`
- Reports/history: `deployments/report.json`, `deployments/history.json`

Scripts:
- `scripts/iac_plan.py`: merge modules + env → `iac/plan.json` (sorted keys, newline-terminated)
- `scripts/iac_apply.py`: simulate apply → `iac/state.json` (idempotent; `--destroy` supported)
- `scripts/release_run.py`: run canary/rollout using fixtures; threshold gate; writes `deployments/report.json`
- `scripts/release_history.py`: append/update `deployments/history.json` by fingerprint (dedupe; stable sort)
- `scripts/release_check.sh`: CI-friendly wrapper (plan → apply → release → history); exits non-zero on threshold violation

Quickstart:
```bash
# IaC plan/apply (staging)
IAC_ENABLED=1 IAC_ENV=staging python3 scripts/iac_plan.py
python3 scripts/iac_apply.py
cat iac/plan.json | jq .
cat iac/state.json | jq .

# Canary rollout (pass)
RELEASE_ENABLED=1 RELEASE_ENV=staging \
ROLL_OUT_THRESH_ERR=0.02 ROLL_OUT_THRESH_P95=800 \
RELEASE_FIXTURES=deployments/fixtures/canary_ok.json \
bash scripts/release_check.sh
cat deployments/report.json | jq .
cat deployments/history.json | jq .

# Canary rollout (fail)
RELEASE_FIXTURES=deployments/fixtures/canary_bad.json \
bash scripts/release_check.sh || echo "gated as expected"
```

Determinism requirements:
- Stable glob discovery; arrays sorted by `id`/`percent`
- No randomness; no network calls
- Timestamps reuse on identical reruns
- JSON outputs sorted keys and newline-terminated
- Idempotent reruns produce identical outputs

Environment toggles:
- `IAC_ENABLED=1` (disable with 0)
- `IAC_ENV=staging|prod`
- `IAC_OUTDIR=iac`
- `RELEASE_ENABLED=1` (disable with 0)
- `RELEASE_ENV` (defaults to `IAC_ENV`)
- `RELEASE_FIXTURES=deployments/fixtures/canary_ok.json` (comma-separated allowed)
- `ROLL_OUT_STEPS=10,50,100`
- `ROLL_OUT_THRESH_ERR=0.02`
- `ROLL_OUT_THRESH_P95=800`
- `RELEASE_ALLOW_WARN_OVERRIDE=0` (reserved)
- `RELEASE_WRITE_KB=0` (1 ingests redacted summaries into local KB)

KB linkage (optional, local-only):
- When `RELEASE_WRITE_KB=1`, `scripts/release_run.py` ingests a redacted summary into KB via in-process orchestrator helpers.

7) Troubleshooting

NumPy build fails / ModuleNotFoundError

Use Python 3.12.5. Do not use 3.13 yet on macOS arm64.

Run: ./scripts/rebuild_env.sh

Docker daemon / socket

Ensure Docker Desktop is running, context set to desktop-linux:
docker context use desktop-linux

GitHub 403 / auth

Use SSH remote or a PAT with repo + workflow scopes.

GITHUB_WRITE_ENABLED=0 forces dry‑run (no writes), good for CI sims.

PR can’t merge (not green)

Approve via orchestrator endpoint (human approval status must be success).

Webhook not firing

Verify smee is running and WEBHOOK_SECRET matches GitHub webhook settings.

8) What’s Next (Phase 11+ Roadmap)

Temporal‑backed orchestration

Persist LangGraph → Temporal workflows; resilience, retries, visibility

Multi‑persona agents (Product, Design, CTO, Eng, Research, Chief of Staff)

Shared memory; role prompts; debate/consensus loop; cost routing

Richer KB

File ingestion (PDF/MD), chunking w/ embeddings; add a vector DB

Observability

OpenTelemetry tracing + structured logs for agent decisions

Security & Guardrails

Secret scanning, model usage policies, repo permission narrowing

Founder cockpit UI

Timeline of runs, PR links, approvals, DoR status, graph state

Policy as Code

Rego / YaML for DoR/DoD; PR templates; codeowners gating

Cost telemetry

Model spend per run/agent; budget alerts

### Budget & Cost Guards (Phase 19)

- Endpoints:
  - `POST /integrations/budget/{run_id}/compute` — compute per‑run/persona tokens and cost, upsert ledger, set `ai-csuite/budget` status, and upsert PR summary with a Budget section. Dry‑run honored when `GITHUB_WRITE_ENABLED=0`.
  - `GET /integrations/budget/{run_id}` — retrieve latest budget snapshot.
  - `POST /integrations/budget/{run_id}/reset` — idempotent reset for demo/tests.
- Env:
  - `BUDGET_ENABLED=1`
  - `BUDGET_WARN_PCT=0.8`, `BUDGET_BLOCK_PCT=1.0`
  - `BUDGET_USD_PER_1K_TOKENS=0.01`
  - `BUDGET_RUN_USD` optional per-run cap (default 0.01)
  - `BUDGET_PERSONAS` (comma‑sep) or `BUDGET_PERSONA_LIMITS` (JSON map of persona→USD)
  - `GITHUB_PR_ENABLED`, `GITHUB_WRITE_ENABLED` respected.
- Curl examples:
  - Compute (dry‑run summary/status):
    ```bash
    curl -s -X POST "${ORCH_BASE:-http://localhost:8000}/integrations/budget/$RUN_ID/compute" \
      -H 'content-type: application/json' \
      -d '{"warn_pct":0.8,"block_pct":1.0,"rate":{"usd_per_1k_tokens":0.01}}'
    ```
    Response includes `status, totals, personas[]` and any simulated GitHub status updates.
  - Read snapshot:
    ```bash
    curl -s "${ORCH_BASE:-http://localhost:8000}/integrations/budget/$RUN_ID"
    ```
  - Reset (tests/demo):
    ```bash
    curl -s -X POST "${ORCH_BASE:-http://localhost:8000}/integrations/budget/$RUN_ID/reset"
    ```


9) Phases 43–46 Overview

Phase 43 — ROI‑Driven Planning
- Endpoints: POST /planning/roi/score, POST /roadmap/suggest
- Value Score merges Attribution + Experiments + cost into basis points; deterministic. Cockpit surfaces Top 5 ROI.

Phase 44 — SaaS Control Plane & Billing
- Endpoints: GET /billing/usage, POST /billing/plan/set, POST /billing/invoice/mock
- Meters per tenant/month; quotas by plan; mock invoices.

Phase 45 — Enterprise Pack
- Endpoints: POST /auth/sso/config, GET /audit/export?fmt=json|csv
- RBAC via X-Role header; SSO config validator; audit export of privileged actions.

Phase 46 — Founder Cockpit 2.0
- Endpoints under /cockpit: experiments, campaigns, audiences, roi; actions: kill-switch, ramp, approve-spend.
- All offline/deterministic; responses stable and sorted.

11) Phases 59–61 — Optimizer, Self‑Healing, Auto‑Vendor Swap

Phase 59 — Cost/Performance Optimizer

- Endpoint: `POST /self/optimize` → analyzes recent run history and produces a deterministic optimization report.
- Output: `apps/orchestrator/orchestrator/self/optimizer_report.json` (sorted keys, newline‑terminated) including baseline cost, recommendations (caching/async/model routing) and a summary section suitable for PR.

Phase 60 — Self‑Healing (Revert & Bisect)

- Endpoints:
  - `POST /incidents/revert` with `{run_id, reason}` → creates `incidents/revert-<id>.json` artifact.
  - `POST /incidents/bisect` with `{run_id, start_sha, end_sha}` → creates `incidents/bisect-<id>.json` artifact.
- Artifacts follow `docs/INCIDENT_PLAYBOOKS.md` guidelines; all outputs are deterministic with sorted keys and trailing newline.

Phase 61 — Auto‑Vendor Swap (Shadow → Ramp)

- Reuses PAL Shadow/Ramp with helper endpoints:
  - `POST /providers/shadow/start/simple` `{capability, candidate}` → shadow id
  - `POST /providers/shadow/compare-once` `{capability}` → deterministic diff summary
  - `POST /providers/ramp/{stage}` `{capability, candidate}` → 5|25|50|100, promotes at 100
- Report: `apps/orchestrator/orchestrator/self/vendor_shadow_report.json` captures mismatches and decision (proceed/hold).

10) Definition of Ready (DoR) / Done (DoD)

DoR: PRD (title, problem, stories), acceptance criteria, success metric, risk/mitigation, design heuristics pass, research summary.

DoD: Tests green, artifacts committed, PR summary updated, statuses green, approved, merged, roadmap updated.

11) Glossary

Run: a single execution for a roadmap item (phase: discovery/delivery)

DoR: Definition of Ready

PR Summary Comment: Marker‑based upsert of a single canonical PR summary