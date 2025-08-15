# AI C‑Suite — Current Status (2025-08-15)

We are at Phase 11 with the following shipped:

- Projects, Roadmap Items, Runs; Discovery (PRD/Design/Research) with DoR
- GitHub PR open/statuses/approve/merge; PR Summary comment upsert; Webhooks
- LangGraph delivery pipeline with Postgres-persisted graph state and resume
  - Early stops via `stop_after` set DB run.status to `paused`
  - `POST /runs/{id}/graph/resume` continues from the next unfinished step
  - `GET /runs/{id}/graph/history` lists per-step attempts (ok/error)

Quick local test:

```bash
./scripts/rebuild_env.sh
./scripts/test_local.sh
```

Quick resume demo:

```bash
# Create project/item/run, then:
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start \
  -H 'content-type: application/json' -d '{"stop_after":"research"}' | jq .

# Status will be paused; resume to finish remaining steps
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/resume -d '{}' | jq .
```

---

# AI C‑Suite — Phase 6 (GitHub PRs from runs)

This phase lets a delivery run:
- create a **feature branch**
- commit discovery artifacts (PRD, design, research, run meta)
- open a **pull request**

It will **skip PR creation** if `GITHUB_TOKEN` is not set, so local tests stay green.

## 1) Configure environment
```bash
cp .env.example .env
# Edit .env, set:
# GITHUB_TOKEN=<a PAT with "repo" scope>

2) Run locally
docker compose up --build

3) Verify GitHub access

Replace <PROJECT_ID> or <REPO_URL> below.

# If your project already has repo_url set:
curl -s -X POST http://localhost:8000/integrations/github/verify \
  -H "content-type: application/json" \
  -d '{"project_id":"<PROJECT_ID>"}' | jq .

# Or verify directly by URL:
curl -s -X POST http://localhost:8000/integrations/github/verify \
  -H "content-type: application/json" \
  -d '{"repo_url":"https://github.com/<owner>/<repo>.git"}' | jq .

4) Create a project pointed at your repo
curl -s -X POST http://localhost:8000/projects \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"Demo","description":"","repo_url":"https://github.com/<owner>/<repo>.git"}' | tee /tmp/p.json
PROJECT_ID=$(jq -r .id </tmp/p.json)

5) Create roadmap item, run, and start (this opens a PR)
curl -s -X POST http://localhost:8000/roadmap-items \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"First Feature"}' | tee /tmp/i.json
ITEM_ID=$(jq -r .id </tmp/i.json)

curl -s -X POST http://localhost:8000/runs \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}' | tee /tmp/r.json
RUN_ID=$(jq -r .id </tmp/r.json)

curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | jq .


If GITHUB_TOKEN and repo_url are set, the response will include pr_url and branch.

6) Fetch PR info later
curl -s http://localhost:8000/runs/$RUN_ID/pr | jq .

7) Tests (outside Docker)
python -m venv .venv && source .venv/bin/activate
pip install -r apps/orchestrator/requirements.txt
pip install pytest
PYTHONPATH=apps/orchestrator pytest -q


---

### 7) Output ONLY this **Command Checklist**

**COMMAND CHECKLIST (paste in terminal):**
```bash
cd ai-csuite

# 1) Set your GitHub token (PAT with "repo" scope)
#    Edit .env and set GITHUB_TOKEN
cp .env.example .env
# open .env in your editor and set GITHUB_TOKEN=...

# 2) Rebuild & run
docker compose up --build

# 3) In another terminal, create a project pointing at your repo
curl -s -X POST http://localhost:8000/projects \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"Demo","description":"","repo_url":"https://github.com/<owner>/<repo>.git"}' | tee /tmp/p.json
PROJECT_ID=$(jq -r .id </tmp/p.json)

# 4) Create roadmap item
curl -s -X POST http://localhost:8000/roadmap-items \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"First Feature"}' | tee /tmp/i.json
ITEM_ID=$(jq -r .id </tmp/i.json)

# 5) Create run
curl -s -X POST http://localhost:8000/runs \
  -H "content-type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}' | tee /tmp/r.json
RUN_ID=$(jq -r .id </tmp/r.json)

# 6) Start run -> discovery (DoR) -> delivery -> PR
curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | tee /tmp/start.json

# 7) Inspect PR metadata
curl -s http://localhost:8000/runs/$RUN_ID/pr | jq .

✅ What success looks like (Phase 6)

With token set & repo_url configured:
/runs/{id}/start returns { ..., "pr_url": "https://github.com/<owner>/<repo>/pull/<n>", "branch": "feature/..." } and /runs/{id}/pr returns PR metadata.

Without token or repo_url:
/runs/{id}/start completes delivery and includes "pr_skipped": "..." — no failure.
```

## Discovery: status vs ensure
- `GET /roadmap-items/{id}/discovery` → **status only** (no side effects)
- `POST /roadmap-items/{id}/discovery/ensure?force=false` → **idempotent create/refresh** of PRD, Design, Research. Returns the same status payload.

## Update a project (e.g., fix repo_url)
```bash
curl -s -X PATCH http://localhost:8000/projects/<PROJECT_ID> \
  -H "content-type: application/json" \
  -d '{"repo_url":"https://github.com/<owner>/<repo>.git"}' | jq .

Dev Doctor
./scripts/dev_doctor.sh --repo https://github.com/<owner>/<repo>.git
```


---

### 7) Output ONLY this **Command Checklist**

**COMMAND CHECKLIST (paste in terminal):**
```bash
cd ai-csuite

# Rebuild & run
docker compose up --build

# 0) Preflight (optional)
./scripts/dev_doctor.sh

# 1) Create a project (REAL repo_url; fix any earlier typos like 'https://https://')
curl -s -X POST http://localhost:8000/projects \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"Demo","description":"","repo_url":"https://github.com/<owner>/<repo>.git"}' | tee /tmp/p.json
PROJECT_ID=$(jq -r .id </tmp/p.json)

# (If you created a bad repo_url previously, fix it:)
# curl -s -X PATCH http://localhost:8000/projects/$PROJECT_ID \
#  -H "content-type: application/json" \
#  -d '{"repo_url":"https://github.com/<owner>/<repo>.git"}' | jq .

# 2) Create a roadmap item
curl -s -X POST http://localhost:8000/roadmap-items \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"First Feature"}' | tee /tmp/i.json
ITEM_ID=$(jq -r .id </tmp/i.json)

# 3) Ensure discovery artifacts (idempotent; add ?force=true to refresh)
curl -s -X POST "http://localhost:8000/roadmap-items/$ITEM_ID/discovery/ensure" | jq .

# 4) Create a run
curl -s -X POST http://localhost:8000/runs \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}' | tee /tmp/r.json
RUN_ID=$(jq -r .id </tmp/r.json)

# 5) Start the run (DoR gate will pass; PR step will run if GITHUB_TOKEN + repo_url are set)
curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | tee /tmp/start.json

# 6) View PR metadata (if created)
curl -s http://localhost:8000/runs/$RUN_ID/pr | jq .

Why this sets you up for success

Clear semantics: No surprises—GET is read‑only, POST does work.

Idempotency: You can “ensure” discovery any time; repeated calls won’t duplicate unless you pass force=true.

Operator control: You can fix project settings (repo_url) without data churn.

Better ergonomics: The dev doctor catches the common “why did this block?” issues (Docker not running, bad repo URL, missing token).

Future‑proof: We didn’t add new DB columns, so no migrations now. When you’re ready for migrations (Alembic), we can add artifact version histories, DoR snapshots, and approval gates without breaking this flow.
```

## Phase 7 — PR merge policy, statuses, approval

This phase publishes GitHub **commit statuses** to your PR’s head SHA:

- `ai-csuite/dor` — `success` if DoR passes, otherwise `failure`
- `ai-csuite/human-approval` — starts `pending`; set to `success` via API to approve
- `ai-csuite/artifacts` — `success` when artifacts are committed

You can control which statuses are **required to merge** via:


GITHUB_REQUIRED_CONTEXTS=ai-csuite/dor,ai-csuite/human-approval


### Endpoints
- `GET /integrations/github/pr/{run_id}/statuses` → current status contexts + `can_merge`
- `POST /integrations/github/pr/{run_id}/approve` → set `ai-csuite/human-approval=success`
- `POST /integrations/github/pr/{run_id}/refresh-status` → recompute DoR, update `ai-csuite/dor`
- `POST /integrations/github/pr/{run_id}/merge` → merges if all required contexts are green

### (Recommended) Branch protection
In your repo settings, protect your default branch and **require status checks**:
- Add: `ai-csuite/dor`, `ai-csuite/human-approval` (and any CI contexts you use)
- Optionally require PR review

This ensures merges via GitHub UI are also gated.

## Phase 8 — Auto-refresh PR artifacts via GitHub webhooks

### Dev-friendly webhook forwarding (Smee)
1) Create a channel at https://smee.io/new and copy its URL.
2) In your GitHub repo → Settings → Webhooks:
   - Payload URL: the **Smee channel URL**
   - Content type: `application/json`
   - Secret: set a secret (also set `GITHUB_WEBHOOK_SECRET` in `.env`)
   - Events: `Pull requests`
3) Export your Smee URL and run the forwarder:
```bash
export SMEE_URL=https://smee.io/<your-channel>
./scripts/smee.sh
```

This forwards GitHub events to http://localhost:8000/webhooks/github.

What happens on PR open/synchronize/reopen

Orchestrator ensures (force) PRD, design, and research for the roadmap item implied by the branch pattern feature/<8hex>-slug.

Artifacts are committed to the PR branch under docs/roadmap/<prefix>-<slug>/.

Commit statuses updated:

ai-csuite/dor → success/failure

ai-csuite/artifacts → success

(human approval untouched)

Manual testing
```bash
curl -s -X POST http://localhost:8000/integrations/github/pr/ensure-artifacts \
  -H "content-type: application/json" \
  -d '{"owner":"<owner>","repo":"<repo>","branch":"feature/<prefix>-<slug>","number":123}' | jq .
```

Optional: Temporal (resumable jobs)

Run Temporal locally with a worker:

```bash
docker compose --profile temporal up --build
```

Worker task queue: ai-csuite

Workflow: RefreshArtifactsWorkflow (delegates to the same ensure endpoint)
Open the UI at http://localhost:8233.

---

## ✅ COMMAND CHECKLIST (paste in terminal)

```bash
cd ai-csuite

# 0) Rebuild with new deps and routes
docker compose up --build

# 1) Set a GitHub webhook secret (same value in GitHub webhook & .env)
#    In .env, set:
#      GITHUB_TOKEN=<your PAT with repo scope>
#      GITHUB_WEBHOOK_SECRET=<your random secret>

# 2) Create a Smee channel and forward webhooks locally
export SMEE_URL=https://smee.io/<your-channel>
./scripts/smee.sh
# (Leave this running)

# 3) In your GitHub repo (jarednwolf/ai-csuite):
#    Settings → Webhooks → Add webhook
#      Payload URL: the Smee channel URL
#      Content type: application/json
#      Secret: same as GITHUB_WEBHOOK_SECRET
#      Events: Pull requests

# 4) Create a project pointing at your repo
curl -s -X POST http://localhost:8000/projects \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"Webhook Demo","description":"","repo_url":"https://github.com/jarednwolf/ai-csuite.git"}' | tee /tmp/p8.json
PROJECT_ID=$(jq -r .id </tmp/p8.json)

# 5) Create roadmap item
curl -s -X POST http://localhost:8000/roadmap-items \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"Webhook Auto-Refresh"}' | tee /tmp/i8.json
ITEM_ID=$(jq -r .id </tmp/i8.json)

# 6) Create & start a run (opens PR as before)
curl -s -X POST http://localhost:8000/runs \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}' | tee /tmp/r8.json
RUN_ID=$(jq -r .id </tmp/r8.json)

curl -s -X POST http://localhost:8000/runs/$RUN_ID/start | jq .

# 7) Make a new commit to the PR branch (or push changes). 
#    The webhook will fire → orchestrator refreshes artifacts → DOR + ARTIFACTS statuses update.

# 8) (Optional) Run Temporal services & worker
docker compose --profile temporal up --build
# Visit Temporal UI at http://localhost:8233
```

What “good” looks like in Phase 8

When you push new commits to the PR branch, Smee forwards the event to your local orchestrator and you see:

- New/updated files under docs/roadmap/<prefix>-<slug>/ committed by the bot.
- ai-csuite/dor + ai-csuite/artifacts statuses updated on the new head commit.
- The manual endpoint /integrations/github/pr/ensure-artifacts works for ad‑hoc refresh.

(Optional) With --profile temporal:

Temporal UI shows RefreshArtifactsWorkflow runs when triggered.

## Phase 8.1 — Auto‑Ensure on Run Start + E2E Tests

### What changed
- `/runs/{id}/start` now **auto‑ensures** PRD/Design/Research artifacts before DoR, so runs don’t block just because discovery was empty.
- Optional toggles:
  - `AUTO_ENSURE_DISCOVERY=1` (default) — disable with `0/false/no` if you want strict mode.
  - `GITHUB_PR_ENABLED=1` (default) — set to `0` to suppress PR creation (useful in tests/CI).

### Run the service
```bash
docker compose up --build

Install test deps (host)
python -m pip install -r requirements-dev.txt

Fast, no‑PR E2E (always safe)
pytest -m e2e -q

Live GitHub E2E (optional)
export GITHUB_TOKEN=ghp_xxx
export E2E_REPO_OWNER=<owner>
export E2E_REPO_NAME=<repo>

pytest -m requires_github -q
```

---

## ✅ Command Checklist (paste in terminal)

```bash
cd ai-csuite

# 1) Rebuild and run
docker compose up --build

# 2) Install test dependencies on host
python -m pip install -r requirements-dev.txt

# 3) Fast test (no PR; validates auto-ensure & non-blocking run start)
pytest -m e2e -q

# 4) (Optional) Live GitHub test — only if you want to exercise PR/status/merge
# export GITHUB_TOKEN=ghp_...
# export E2E_REPO_OWNER=jarednwolf
# export E2E_REPO_NAME=ai-csuite
# pytest -m requires_github -q
```

What you should see

pytest -m e2e: green test confirming /runs/{id}/start succeeds and skips PR (because repo_url is empty), proving auto‑ensure works.

pytest -m requires_github (if you run it): green test that opens a PR, shows statuses, requires human approval, and then merges.

## Phase 9 — CI + PR Summary Comments + Webhook Simulation

### What’s new
- Orchestrator posts/updates a **PR summary comment** with DoR status and links to artifacts.
- **Dry-run** mode for CI: `GITHUB_WRITE_ENABLED=0` skips all GitHub writes.
- **CI workflow** runs local E2E + webhook simulation on every PR (`.github/workflows/ci.yml`).
- **Live E2E** workflow (`.github/workflows/live-e2e.yml`) can be triggered manually to validate the full GitHub integration.

### Local test scripts
```bash
# Start services
docker compose up --build

# Local tests (no GitHub writes)
./scripts/test_local.sh

# Live tests (requires token)
export GITHUB_TOKEN=<token-with-repo-scope>
export E2E_REPO_OWNER=<owner>
export E2E_REPO_NAME=<repo>
./scripts/test_live.sh

Manual endpoints

Refresh PR comment: POST /integrations/github/pr/{run_id}/comment/refresh
```

---

## ✅ Command Checklist (local)

```bash
cd ai-csuite

# 0) Rebuild with latest changes
docker compose up --build

# 1) Local tests (no GitHub writes needed)
./scripts/test_local.sh

# 2) Live tests (optional) — opens a real PR, comments, approves, merges
export GITHUB_TOKEN=ghp_xxx
export E2E_REPO_OWNER=jarednwolf
export E2E_REPO_NAME=ai-csuite
./scripts/test_live.sh
```

What to expect

On PR open (Phase 7/8 path): PR gets statuses + a Summary comment with DoR result and links under docs/roadmap/....

On pushes to the PR branch: webhook (or manual ensure) refreshes artifacts, updates statuses, and updates the same summary comment (identified by a hidden marker).

CI runs your safe tests on every PR; Live E2E is a manual button when you want to validate against GitHub.

## Phase 10 — LangGraph multi‑agent pipeline

**What it does**
- Runs a parameterized, reusable graph per roadmap item with nodes:
  `Product → Design → Research → CTO Plan → Engineer → QA (loop) → Release`.
- Uses LangGraph checkpointing (`LANGGRAPH_CHECKPOINT=sqlite|memory`).

**Env**
- `LANGGRAPH_CHECKPOINT=sqlite` (default) or `memory`.

**API**
- `POST /runs/{run_id}/graph/start`
  - Body: `{"force_qa_fail": false, "max_qa_loops": 2}`
- `GET /runs/{run_id}/graph/state`

**Try it**
```bash
# Start services
docker compose up --build

# Create project/item/run as usual, then:
curl -s -X POST http://localhost:8000/runs/<RUN_ID>/graph/start \
  -H "content-type: application/json" \
  -d '{"force_qa_fail": false, "max_qa_loops": 2}' | jq .

curl -s http://localhost:8000/runs/<RUN_ID>/graph/state | jq .
```

Automated tests

```bash
./scripts/test_local.sh
```

---

## ✅ Command Checklist (paste into your terminal)

```bash
cd ai-csuite

# 1) Rebuild to install new orchestrator deps
docker compose up --build

# 2) (Optional) Confirm API is healthy
curl -s http://localhost:8000/healthz

# 3) Run the local test suite (includes Phase 10 tests)
./scripts/test_local.sh

# 4) Manual smoke (if you want):
# Create project
curl -s -X POST http://localhost:8000/projects \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","name":"LG Demo","description":"","repo_url":""}' | tee /tmp/lg_proj.json
PROJECT_ID=$(jq -r .id </tmp/lg_proj.json)

# Create roadmap item
curl -s -X POST http://localhost:8000/roadmap-items \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","title":"LG Feature"}' | tee /tmp/lg_item.json
ITEM_ID=$(jq -r .id </tmp/lg_item.json)

# Create run
curl -s -X POST http://localhost:8000/runs \
 -H "content-type: application/json" \
 -d '{"tenant_id":"00000000-0000-0000-0000-000000000000","project_id":"'"$PROJECT_ID"'","roadmap_item_id":"'"$ITEM_ID"'","phase":"delivery"}' | tee /tmp/lg_run.json
RUN_ID=$(jq -r .id </tmp/lg_run.json)

# Start graph (happy path)
curl -s -X POST http://localhost:8000/runs/$RUN_ID/graph/start \
  -H "content-type: application/json" \
  -d '{"force_qa_fail": false, "max_qa_loops": 2}' | jq .

# State
curl -s http://localhost:8000/runs/$RUN_ID/graph/state | jq .
```

Notes & Future Hooks

This graph uses stubbed node logic so it’s fast and stable in CI. In Phase 12, we’ll attach a Runner that applies real code patches and executes tests in a sandboxed container; the QA loop will then be fully “self-correcting.”

If you want the Release node to always open a PR when repo_url is set, it already calls your open_pr_for_run (skips safely if not possible).

The graph is project‑agnostic and item‑aware (it’s parameterized by tenant_id, project_id, roadmap_item_id), so you can reuse it for every new roadmap item.