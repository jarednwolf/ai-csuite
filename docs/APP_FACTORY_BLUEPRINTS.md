AI‑CSuite — App Factory Blueprints

Last updated: 2025‑08‑15

Blueprints let agents scaffold from scratch or extend an existing repo, end‑to‑end, while honoring typed artifacts (PRD/Design/Research/Plan/QA), PR gating, and resume semantics. This spec defines the manifest, the scaffolder workflow, and acceptance tests.

See: Agent Operating Manual (contracts & gates)
; Phase 11–16 APIs (resume/history, statuses)
; Cockpit controls
; Cursor patch etiquette
.

1) Blueprint Manifest (JSON)
{
  "id": "web-crud-fastapi-postgres-react",
  "name": "Web CRUD (FastAPI + Postgres + React)",
  "description": "Auth, CRUD, list/detail, search, audit logs, seeded data",
  "stack": {
    "backend": {"runtime": "python3.12", "framework": "fastapi", "db": "postgres"},
    "frontend": {"framework": "react"},
    "infra": {"containers": true, "iac": "terraform", "preview_envs": true}
  },
  "capabilities": ["auth", "crud", "search", "uploads", "email", "metrics"],
  "quality_gates": {
    "a11y_min": 80,
    "e2e_cov_min": 0.7,
    "perf_budget_ms": 1500
  },
  "scaffold": [
    {"step": "init_repo_or_branch"},
    {"step": "create_backend_service"},
    {"step": "create_frontend_app"},
    {"step": "db_migrations_and_seed"},
    {"step": "wire_ci_cd_and_iac"},
    {"step": "add_e2e_tests"},
    {"step": "open_pr_and_request_gates"}
  ],
  "deploy_targets": ["preview", "staging", "prod"]
}

Required fields

quality_gates map into DoR/DoD checks and PR statuses.

scaffold steps must be idempotent and resumable; record to /graph/history.

2) Scaffolder Workflow (orchestrated by AI‑CSuite)

Plan: CTO persona selects a blueprint based on PRD; emits TechPlan.json with tasks & risks.

Scaffold: ENG persona executes steps (idempotent); open PR; orchestrator sets statuses; PR summary upsert.

Verify: QA persona runs unit + e2e + a11y; posts QAReport.json; gates must pass.

Deploy: CoS triggers approve/merge via cockpit; preview→staging→prod promotion.

3) Acceptance Tests (per blueprint)

Contract tests: endpoints (CRUD + auth), migrations, seed data load.

E2E: create/edit/delete happy paths; a11y score ≥ a11y_min.

Perf: p95 page load ≤ perf_budget_ms.

Observability: traces present; dashboard tiles created for the app.

4) Initial Blueprint Set

web-crud-fastapi-postgres-react — general dashboard/ordering/booking.

mobile-crud-expo-supabase — cross‑platform list/detail with auth & sync.

ai-chat-agent-web — chat UI + retrieval; eval harness for answer quality.

realtime-media-web — upload/stream; background processing queue.

Add manifests under blueprints/ and register them in the orchestrator so Product/CTO personas can choose at DoR time.

5) PR & Gating Policy (applies to all blueprints)

Orchestrator must set and verify: ai‑csuite/dor, ai‑csuite/human‑approval, ai‑csuite/artifacts.

Cockpit shows status + cost; merge only if all green and budget not exceeded.

For Budget status and summary during factory runs, see the Budget endpoints in AI-CSUITE_HANDOFF.md and Phase 19 checklist. The `ai-csuite/budget` context is optional and can be made required via `GITHUB_REQUIRED_CONTEXTS`.

6) Operating Notes

Resume/retry at any scaffold step; ensure idempotent file writes and migrations.

ADR any one‑way door decisions (framework change, schema choice).

7) How Cursor should implement blueprints

Use atomic patch blocks with complete files and matching tests.

Update docs/PHASE_TRACKING_CHECKLIST.md when a blueprint is added or its gates are met.

8) Example: Tiny CRUD acceptance (backend)
{
  "tests": [
    {"name": "healthz", "status": "pass"},
    {"name": "create_item", "status": "pass"},
    {"name": "get_item", "status": "pass"},
    {"name": "update_item", "status": "pass"},
    {"name": "delete_item", "status": "pass"}
  ],
  "defects": [],
  "recommendation": "proceed"
}


This maps directly to QAReport.json in the Agent Manual.

9) Next Steps

Land the initial manifest & scaffolder.

Try locally (dry‑run, no GH writes):

```bash
export GITHUB_WRITE_ENABLED=0
curl -s http://localhost:8000/blueprints | jq .
curl -s http://localhost:8000/blueprints/web-crud-fastapi-postgres-react | jq .

curl -s -X POST http://localhost:8000/app-factory/scaffold \
  -H 'content-type: application/json' \
  -d '{
    "blueprint_id": "web-crud-fastapi-postgres-react",
    "target": {"mode": "existing_repo", "owner": "'$E2E_REPO_OWNER'", "name": "'$E2E_REPO_NAME'", "default_branch": "main"},
    "run_id": "op-local-demo"
  }' | jq .
```

Cockpit create-from-blueprint

- Open the Founder Cockpit page `/ui/blueprints` to select a blueprint id (sorted) and scaffold via the existing API. In dry‑run (`GITHUB_WRITE_ENABLED=0`), owner/name may be omitted for a local simulation; the response includes an `op_id` you can open at `/ui/run/<op_id>`.
- This UI uses only in‑process endpoints and preserves the manifest contract; no external network calls are made.

10) Quality Gates Validator (Phase 26)

- Validate manifests and produce a deterministic report summarizing capabilities and `quality_gates` per blueprint.
- Scripts:
  - `scripts/blueprints_report.py` → `blueprints/report.json`
  - `scripts/blueprints_check.sh` → exits non‑zero on errors
- Determinism:
  - Sorted discovery by filename; blueprint list sorted by `id`
  - Stable keys and newline termination
  - Timestamps are reused when inputs unchanged

Add preview env smoke tests to CI.

Extend cockpit with “Create App from Blueprint” (select manifest, enter name, target env).

Preview integration (Phase 18)

In dry‑run, scaffolded runs stage a placeholder `ai-csuite/preview-smoke` status as pending. The real status is managed by the Preview service endpoints:

- `POST /integrations/preview/{run_id}/deploy` — sets preview to pending for the branch
- `POST /integrations/preview/{run_id}/smoke` — marks success/failure; updates PR summary with a Preview section (simulated when `GITHUB_WRITE_ENABLED=0`)