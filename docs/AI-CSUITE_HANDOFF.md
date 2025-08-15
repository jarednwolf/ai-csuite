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

LangGraph: langgraph>=0.2.0,<1.0, langchain-core>=0.2.0,<1.0

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
  -d '{"tenant_id":"00000000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}')

RUN_ID=$(echo "$RUN" | jq -r .id)
curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | jq .


LangGraph endpoints

curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start | jq .
curl -s http://localhost:8000/runs/$RUN_ID/graph/state | jq .
# Early stop / resume demo:
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start \
  -H 'content-type: application/json' -d '{"stop_after":"research"}' | jq .
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/resume -d '{}' | jq .

5) GitHub Flow, Statuses, Webhooks

PR statuses required

ai-csuite/dor — DoR passed

ai-csuite/human-approval — requires explicit human approval call

ai-csuite/artifacts — AI‑CSuite committed artifacts

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

6) Tests & Scripts

Local (safe)

./scripts/test_local.sh
# runs: health, phases 3–5, 9–11, webhook simulation (dry-run)


Live GitHub (creates real PRs)

export GITHUB_TOKEN=<PAT>
export E2E_REPO_OWNER=jarednwolf
export E2E_REPO_NAME=ai-csuite
export ORCH_BASE=http://localhost:8000
pytest -m requires_github -q


Examples (individual tests)

pytest apps/orchestrator/tests/test_phase7_statuses_merge.py -q
pytest apps/orchestrator/tests/test_phase10_graph_happy_path.py -q


CI

.github/workflows/ci.yml — local E2E + webhook sim with dry‑run

.github/workflows/live-e2e.yml — manual, requires secrets to talk to GH

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

9) Definition of Ready (DoR) / Done (DoD)

DoR: PRD (title, problem, stories), acceptance criteria, success metric, risk/mitigation, design heuristics pass, research summary.

DoD: Tests green, artifacts committed, PR summary updated, statuses green, approved, merged, roadmap updated.

10) Glossary

Run: a single execution for a roadmap item (phase: discovery/delivery)

DoR: Definition of Ready

PR Summary Comment: Marker‑based upsert of a single canonical PR summary