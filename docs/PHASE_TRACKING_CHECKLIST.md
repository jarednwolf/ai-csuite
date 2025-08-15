# AI-CSuite — Phase Tracking Checklist

_Last updated: 2025-08-15_

Use this document to track progress through Phases 1–16.  
Each phase contains: **Goal**, **Key Changes**, **Tests**, **Expected Outcomes**, and **Success Criteria**.  
Mark `[x]` when complete.

---

## Phase 1 — API Skeleton & Runs Resource
- [x] **Goal:** Establish FastAPI orchestrator with `/runs` endpoint and basic project scaffolding.
- **Key Changes:**
  - Create FastAPI app structure.
  - Implement `/healthz` and `/runs` CRUD.
  - Set up initial Postgres schema for runs.
- **Tests:**  
  - [`apps/orchestrator/tests/test_health.py`](../apps/orchestrator/tests/test_health.py)  
  - [`scripts/test_local.sh`](../scripts/test_local.sh)
- **Expected Outcomes:**
  - Orchestrator can accept and store run metadata.
- **Success Criteria:**
  - Local `docker compose up` passes health check.
  - All Phase 1 tests green.

---

## Phase 2 — Projects & Roadmap Items
- [x] **Goal:** Add `/projects` and `/roadmap-items` resources.
- **Key Changes:**
  - DB tables and models for projects & items.
  - Link roadmap items to projects and runs.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase3_api.py`](../apps/orchestrator/tests/test_phase3_api.py)
- **Expected Outcomes:**
  - Runs have linked project and roadmap context.
- **Success Criteria:**
  - Can create project → item → run from API calls.

---

## Phase 3 — Discovery & DoR Artifacts
- [x] **Goal:** Introduce `discovery/ensure` endpoint and PRD.json generation.
- **Key Changes:**
  - PRD contract validator.
  - Orchestrator auto-generates minimal PRD.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase4_discovery.py`](../apps/orchestrator/tests/test_phase4_discovery.py)
- **Expected Outcomes:**
  - Roadmap items have DoR-ready PRD.
- **Success Criteria:**
  - Generated PRD passes schema validation.

---

## Phase 4 — Design & Research Artifacts
- [x] **Goal:** Add DesignReview.json and ResearchSummary.json generation.
- **Key Changes:**
  - Contracts and validators for design & research.
  - Orchestrator stores artifacts with run.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase4_discovery.py`](../apps/orchestrator/tests/test_phase4_discovery.py)
- **Expected Outcomes:**
  - DoR can be evaluated for product, design, and research.
- **Success Criteria:**
  - `/discovery/ensure` produces all three artifacts.

---

## Phase 5 — Knowledge Base Ingest/Search
- [x] **Goal:** Enable KB ingestion and retrieval for artifact citations.
- **Key Changes:**
  - Basic KB store (Postgres/pgvector).
  - Simple text chunking & search endpoints.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase5_kb.py`](../apps/orchestrator/tests/test_phase5_kb.py)
- **Expected Outcomes:**
  - Artifacts include KB citations.
- **Success Criteria:**
  - Search returns relevant results for sample queries.

---

## Phase 6 — GitHub PR Creation
- [x] **Goal:** Orchestrator can open feature branch PRs for roadmap items.
- **Key Changes:**
  - GitHub API integration for PR create.
  - Branch naming convention enforcement.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase7_statuses_merge.py`](../apps/orchestrator/tests/test_phase7_statuses_merge.py) (covers PR open + statuses)
  - [`scripts/test_live.sh`](../scripts/test_live.sh) (dry-run mode in CI)
- **Expected Outcomes:**
  - New PRs created with linked branch & artifacts.
- **Success Criteria:**
  - Live token test opens PR in test repo.

---

## Phase 7 — PR Statuses & Approvals
- [x] **Goal:** Implement required GitHub PR statuses and orchestrator approval/merge endpoints.
- **Key Changes:**
  - `ai-csuite/dor`, `ai-csuite/human-approval`, `ai-csuite/artifacts` status checks.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase7_statuses_merge.py`](../apps/orchestrator/tests/test_phase7_statuses_merge.py)
- **Expected Outcomes:**
  - Orchestrator can gate merges on statuses.
- **Success Criteria:**
  - Green statuses allow merge via orchestrator.

---

## Phase 8 — Webhooks Integration
- [x] **Goal:** Process GitHub push & pull_request webhooks via smee tunnel for local dev.
- **Key Changes:**
  - `/webhooks/github` endpoint.
  - Webhook secret validation.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase9_webhook_sim.py`](../apps/orchestrator/tests/test_phase9_webhook_sim.py) (simulation used in CI/local)
- **Expected Outcomes:**
  - Artifacts refresh and statuses recompute on events.
- **Success Criteria:**
  - Local smee + push triggers orchestrator update.

---

## Phase 9 — PR Summary Comment Upsert
- [x] **Goal:** Maintain a single canonical PR summary comment.
- **Key Changes:**
  - Marker-based detection/upsert.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase9_pr_comment.py`](../apps/orchestrator/tests/test_phase9_pr_comment.py)
  - [`apps/orchestrator/tests/test_phase9_summary_md.py`](../apps/orchestrator/tests/test_phase9_summary_md.py)
- **Expected Outcomes:**
  - PR summary always up-to-date without duplicates.
- **Success Criteria:**
  - Multiple runs update same comment.

---

## Phase 10 — LangGraph Pipeline
- [x] **Goal:** Orchestrator runs LangGraph pipelines for delivery phases.
- **Key Changes:**
  - `/runs/{id}/graph/start` and `/graph/state` endpoints.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase10_graph_happy_path.py`](../apps/orchestrator/tests/test_phase10_graph_happy_path.py)
  - [`apps/orchestrator/tests/test_phase10_graph_backtrack.py`](../apps/orchestrator/tests/test_phase10_graph_backtrack.py)
- **Expected Outcomes:**
  - Multi-step agent execution managed in orchestrator.
- **Success Criteria:**
  - Pipeline completes and artifacts pass gates.

---

## Phase 11 — LangGraph State Persistence (Postgres) + Resume/Retry
- [x] **Goal:** Persist LangGraph state in Postgres (JSONB per `run_id` + step index); add resume endpoint, retries with exponential backoff (max 3), and history. Supports pause/resume semantics.
- **Key Changes:**
  - DB migration: `graph_states` table (JSONB state, logs, attempt counters).
  - Service/repo layer in `orchestrator/ai_graph/` to persist and load state.
  - API: `POST /runs/{id}/graph/resume`, `GET /runs/{id}/graph/history`.
  - Retry/backoff policy around failing steps.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase11_graph_happy_path.py`
  - `apps/orchestrator/tests/test_phase11_resume.py` (also covers: resume after stop completes, resume when nothing left → 400, resume twice after completion → 400)
  - `apps/orchestrator/tests/test_phase11_retry_exhaust.py`
- **Expected Outcomes:**
  - Runs can be resumed from the last successful step after process restarts.
  - Failing steps retry up to 3 times with exponential backoff.
  - Stepwise history of execution/logs is queryable.
- **Success Criteria:**
  - All Phase 11 tests green locally and in CI. (Local: 10 tests passed)

---

## Phase 12 — Multi-Persona Agents
- [x] **Goal:** Each role (CoS, HP, DL, RL, CTO, ENG, QA) runs as separate agent with shared memory.
- **Key Changes:**
  - Agent prompt templates per role; orchestrator shared_memory passed across steps and persisted for resume.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase12_personas.py`](../apps/orchestrator/tests/test_phase12_personas.py)
- **Expected Outcomes:**
  - Agents collaborate and enforce typed handoffs.
- **Success Criteria:**
  - Run completes with all personas producing artifacts; shared_memory preserved across resume.

---

## Phase 13 — Richer KB + File Ingestion
- [x] **Goal:** Ingest PDFs/MD with chunking and embeddings.
- **Key Changes:**
  - File ingestion endpoint (`POST /kb/ingest-file`) for markdown/pdf/text.
  - Local-only PDF parsing via `pypdf`; deterministic embeddings.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase13_kb_files.py`](../apps/orchestrator/tests/test_phase13_kb_files.py)
- **Expected Outcomes:**
  - Agents retrieve richer context for artifacts.
- **Success Criteria:**
  - Search returns file-derived KB entries.

---

## Phase 14 — Observability & Telemetry
- [x] **Goal:** Add OpenTelemetry traces, logs, and cost metrics.
- **Key Changes:**
  - Structured logging and tracing hooks.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase14_observability.py`](../apps/orchestrator/tests/test_phase14_observability.py)
  - Added to `scripts/test_local.sh` suite
- **Expected Outcomes:**
  - Full visibility into run execution and cost.
- **Success Criteria:**
  - Dashboard shows per-run metrics.

---

## Phase 15 — Security & Guardrails
- [x] **Goal:** Implement secret scanning, permission narrowing, and policy enforcement.
- **Key Changes:**
  - SAST/secrets job in CI.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase15_security.py`](../apps/orchestrator/tests/test_phase15_security.py)
- **Expected Outcomes:**
  - Security violations blocked before merge.
- **Success Criteria:**
  - Guardrails catch and block bad commits.

---

## Phase 16 — Founder Cockpit UI
- [x] **Goal:** Build UI for timeline, statuses, approvals, graph state.
- **Key Changes:**
  - Web frontend consuming orchestrator API.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase16_ui.py`](../apps/orchestrator/tests/test_phase16_ui.py)
- **Expected Outcomes:**
  - Founder can manage runs visually.
- **Success Criteria:**
  - All run management actions possible via UI.
