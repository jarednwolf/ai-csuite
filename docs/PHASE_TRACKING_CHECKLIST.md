# AI-CSuite — Phase Tracking Checklist

_Last updated: 2025-08-16_

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

---

## Phase 17 — App Factory: Blueprint Registry & Scaffolder
- [x] **Goal:** Let agents scaffold new apps (new repo or existing branch) from a **blueprint manifest**, open a PR, and pass gates.
- **Key Changes:**
  - `blueprints/*.json` registry with Pydantic validation and versioning.
  - API: `GET /blueprints`, `GET /blueprints/{id}`; manifest validator.
  - Scaffolder service: generate backend/front-end/IaC/CI, seed data, tests; open PR; idempotent steps recorded in `/graph/history`.
  - PR summary upsert and required statuses set by orchestrator.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase17_blueprints_registry.py`](../apps/orchestrator/tests/test_phase17_blueprints_registry.py)  
  - [`apps/orchestrator/tests/test_phase17_scaffolder.py`](../apps/orchestrator/tests/test_phase17_scaffolder.py)
- **Expected Outcomes:**
  - Agents select a blueprint and produce a PR with runnable app skeleton and tests.
- **Success Criteria:**
  - PR opens with CI configured; scaffolder steps show in history; gates pass in dry-run.

---

## Phase 18 — Preview Environments & Smoke Gate
- [x] **Goal:** Every PR spins up an **ephemeral preview** with a required smoke-test status (e.g., `ai-csuite/preview-smoke`).

Phase 18 — Preview Environments & Smoke Gate

- Endpoints:
  - `POST /integrations/preview/{run_id}/deploy`
  - `POST /integrations/preview/{run_id}/smoke`
  - `GET /integrations/preview/{run_id}`
- Service: `apps/orchestrator/orchestrator/services/preview.py`
- Router: `apps/orchestrator/orchestrator/api/preview_endpoints.py`
- GitHub integration helpers extended in `apps/orchestrator/orchestrator/integrations/github.py` to add `ai-csuite/preview-smoke` and marker comment upsert by branch.
- Tests: `apps/orchestrator/tests/test_phase18_preview_smoke.py`
- **Key Changes:**
  - CI job to build/deploy preview env per PR; teardown on close/merge.
  - Health check endpoint and one happy-path E2E; report status back to PR.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase18_preview_smoke.py`](../apps/orchestrator/tests/test_phase18_preview_smoke.py)
- **Expected Outcomes:**
  - Merges are gated on preview smoke success.
- **Success Criteria:**
  - New PRs show preview URL and green smoke status before merge.

---

## Phase 19 — Budget & Cost Guards (Tokens/$)
- [x] **Goal:** Enforce per-run/persona token/$ **budgets** with soft warnings and hard blocks; surface costs in PR summary & cockpit.
- **Key Changes:**
  - Cost meter aggregation; thresholds (warn at 80%, block at 100%).
  - Status (optional) `ai-csuite/budget` + PR summary budget bar; cockpit tiles.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase19_budget_aggregation.py`](../apps/orchestrator/tests/test_phase19_budget_aggregation.py)  
  - [`apps/orchestrator/tests/test_phase19_budget_status.py`](../apps/orchestrator/tests/test_phase19_budget_status.py)
- **Endpoints:**
  - `POST /integrations/budget/{run_id}/compute`
  - `GET /integrations/budget/{run_id}`
  - `POST /integrations/budget/{run_id}/reset`
- **Expected Outcomes:**
  - Runs that exceed budget cannot merge until approved or adjusted.
- **Success Criteria:**
  - PRs display costs; thresholds trigger statuses; cockpit reflects real totals.
  - `ai-csuite/budget` status visible on PRs (dry‑run simulated when writes disabled).

---

## Phase 20 — Ops Readiness: SLOs, Alerts & Runbooks
- [x] **Goal:** Define SLOs and wire **alerts** with actionable **runbooks**.
- **Key Changes:**
  - SLOs: API availability, queue latency p95, retry success rate.
  - Alerts: SLO burn, retry-exhaust, PR gating stuck, budget overflow.
  - Runbooks for webhook failures, GH rate limits, graph loops, rollback.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase20_metrics_alerts.py`](../apps/orchestrator/tests/test_phase20_metrics_alerts.py)
- **Expected Outcomes:**
  - On-call can resolve common incidents using runbooks.
- **Success Criteria:**
  - Synthetic failure triggers alerts; dashboards show SLOs.

---

## Phase 21 — Supply Chain & Build Integrity
- [x] **Goal:** Reproducible builds with **lockfiles, SBOM, license scan**, pinned base images.
- **Key Changes:**
  - Lockfiles: `scripts/gen_lockfiles.py` → `apps/orchestrator/requirements.lock.txt`, `requirements-dev.lock.txt`.
  - SBOM: `scripts/sbom_gen.py` → `sbom/orchestrator-packages.json`.
  - Licenses: `scripts/license_check.py` → `sbom/licenses.json` with allowlist.
  - Pins: Dockerfiles base images pinned; `.python-version` alignment; CI helper.
- **Scripts:**
  - [`scripts/supply_chain_check.sh`](../scripts/supply_chain_check.sh)
  - [`scripts/gen_lockfiles.py`](../scripts/gen_lockfiles.py)
  - [`scripts/sbom_gen.py`](../scripts/sbom_gen.py)
  - [`scripts/license_check.py`](../scripts/license_check.py)
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase21_supply_chain.py`](../apps/orchestrator/tests/test_phase21_supply_chain.py)
- **Expected Outcomes:**
  - Deterministic builds; local-only SBOM; visible license compliance.
- **Success Criteria:**
  - Local script and tests fail on drift/unpinned deps or disallowed licenses.

---

## Phase 22 — Policy-as-Code Governance
- [x] **Goal:** Enforce local, deterministic Policy-as-Code gates for DoR/DoD, approvals, statuses, budget, licenses.
- **Key Changes:**
  - Local JSON policy bundle `policies/merge_gates.json` and evaluator.
  - Facts normalizer `scripts/policy_input_collect.py` → `policy/facts.json`.
  - Evaluator `scripts/policy_eval.py` → `policy/report.json`.
  - Orchestrator script `scripts/policy_check.sh` for CI/local.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase22_policy_gates.py`](../apps/orchestrator/tests/test_phase22_policy_gates.py)
- **Expected Outcomes:**
  - Non-compliant merges blocked with clear reasons; idempotent artifacts.
- **Success Criteria:**
  - Policy scripts local-only; deterministic outputs; override behavior for warns.

---

## Phase 23 — Compliance Hardening (Secrets, PII/PHI, Audit)
- [x] **Goal:** Strengthen **secret scanning**, **redaction**, and **audit logging**; least-privilege tokens.
- **Key Changes:**
  - Local-only secrets scanner and reports, deterministic redaction helpers, append-only audit logs with redacted details.
  - Wrapper script `scripts/compliance_check.sh`; env toggles documented.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase23_redaction_audit.py`](../apps/orchestrator/tests/test_phase23_redaction_audit.py)
- **Artifacts:**
  - Data: `compliance/regexes.json`, `compliance/test_vectors.json`
  - Reports: `compliance/secrets_report.json`, `compliance/redaction_report.json`, `compliance/audit_report.json`
- **Expected Outcomes:**
  - No plaintext secrets; auditable actions; compliant, deterministic logging and reports.
- **Success Criteria:**
  - Wrapper passes when clean; fails on block findings; audit rows present for exercised flows.

---

## Phase 24 — Evaluation Harness & Golden Tasks
- [x] **Goal:** Deterministic, offline evaluation harness with golden tasks, per-suite scoring, reports, and CI wrapper.
- **Key Changes:**
  - Scripts: `scripts/eval_run.py`, `scripts/eval_history.py`, `scripts/eval_check.sh`
  - Golden bundles: `eval/golden/ai-chat-agent-web.json`, `eval/golden/web-crud-fastapi-postgres-react.json`
  - Stable outputs: `eval/report.json`, `eval/history.json` (sorted keys, newline-terminated)
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase24_eval_harness.py`](../apps/orchestrator/tests/test_phase24_eval_harness.py)
- **Expected Outcomes:**
  - Idempotent re-runs, deterministic ordering, offline execution, threshold gating.
- **Success Criteria:**
  - Wrapper exits non-zero when any suite score < threshold; optional KB ingestion is deterministic and redacted.

---

## Phase 25 — IaC & Environment Provisioning + Progressive Delivery
- [x] **Goal:** Deterministic, local-only IaC simulator (plan/apply) and progressive delivery harness with canary gating.
- **Key Changes:**
  - IaC manifests: `iac/modules/core.json`, `iac/environments/{staging,prod}.json`.
  - Scripts: `scripts/iac_plan.py`, `scripts/iac_apply.py`, `scripts/release_run.py`, `scripts/release_history.py`, wrapper `scripts/release_check.sh`.
  - Rollout fixtures: `deployments/fixtures/{canary_ok,canary_bad}.json`.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase25_iac_release.py`](../apps/orchestrator/tests/test_phase25_iac_release.py)
- **Expected Outcomes:**
  - Deterministic, idempotent artifacts: `iac/plan.json`, `iac/state.json`, `deployments/report.json`, `deployments/history.json` (sorted keys, newline-terminated).
  - Clear gating failures with non-zero exit on violations.
- **Success Criteria:**
  - Wrapper exits non-zero on threshold violations; reruns with unchanged inputs produce identical outputs.

---

## Phase 26 — Blueprint Library Expansion & Quality Gates
- [x] **Goal:** Add more blueprints with **explicit gates**.
- **Key Changes:**
  - Added manifests: `mobile-crud-expo-supabase`, `realtime-media-web` (alongside existing `ai-chat-agent-web`).
  - Deterministic validator/report and wrapper: `scripts/blueprints_report.py`, `scripts/blueprints_check.sh` → `blueprints/report.json`.
  - Offline only, idempotent outputs (sorted keys, newline termination).
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase26_blueprint_manifests.py`](../apps/orchestrator/tests/test_phase26_blueprint_manifests.py)
- **Expected Outcomes:**
  - Agents can build a wider class of apps out-of-the-box; local gates are transparent and deterministic.
- **Success Criteria:**
  - Wrapper exits non-zero on manifest errors or gate violations; reruns unchanged are identical.

---

## Phase 27 — Cockpit UX: Create-from-Blueprint & Budget Controls
- [x] **Goal:** Cockpit adds **“Create App from Blueprint”** flow and **budget tiles**.
- **Key Changes:**
  - UI to pick blueprint & target env; show costs, statuses, approvals.
  - Escalation buttons (autonomy level, ADR links) and PR links.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase27_cockpit_blueprint_ui.py`](../apps/orchestrator/tests/test_phase27_cockpit_blueprint_ui.py)
- **Expected Outcomes:**
  - Human can initiate/monitor factory builds; budget and gates are visible.
- **Success Criteria:**
  - UI exposes deterministic create-from-blueprint and budget compute controls; endpoints used are local-only; lists sorted; dry‑run respected.

---

## Phase 28 — Multi-Run Scale: Scheduling, Priorities & Quotas
- [x] **Goal:** Scale to many concurrent runs with **fairness and quotas**.
- **Key Changes:**
  - Priority queues; concurrency controls; per-tenant quotas; backpressure.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase28_scheduler_quotas.py`](../apps/orchestrator/tests/test_phase28_scheduler_quotas.py)
- **Expected Outcomes:**
  - High throughput without starvation; predictable SLAs.
- **Success Criteria:**
  - Stress tests meet throughput & fairness targets.

---

## Phase 29 — Partner Integration Framework (APIs, Mocks, Rate Limits)
- [x] **Goal:** Standardize external API integrations with **wrappers, mocks, and rate-limit handling**.
- **Key Changes:**
  - Integration adapters with retry/backoff; sandbox mocks; contract tests.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase29_integrations.py`](../apps/orchestrator/tests/test_phase29_integrations.py)
- **Expected Outcomes:**
  - Faster partner onboarding; reliable calls under limits/failures.
- **Success Criteria:**
  - Contract tests pass; rate-limit simulations recover cleanly.

---

## Phase 30 — Postmortem Automation & KB Ingest
- [x] **Goal:** Auto-generate **postmortems** and ingest artifacts into KB for learning loops.
- **Key Changes:**
  - Postmortem generator (defects, retries, costs, ADR links); KB ingestion.
- **Tests:**  
  - [`apps/orchestrator/tests/test_phase30_postmortem_kb.py`](../apps/orchestrator/tests/test_phase30_postmortem_kb.py)
- **Expected Outcomes:**
  - Institutional memory improves; faster iteration over time.
- **Success Criteria:**
  - Postmortems created per run; KB search surfaces lessons next time.

---

## Phase 31 — Provider Abstraction Layer (PAL) & Conformance Harness
- [ ] **Goal:** Make every external tool swappable behind strict capability interfaces with golden conformance tests.
- **Key Changes:**
  - Define `providers/` interfaces: `AdsProvider`, `LifecycleProvider`, `ExperimentsProvider`, `CDPProvider`, `VectorStore`, `LLMObservabilityProvider`, `LLMGateway`.
  - Create **Conformance Kit**: fixtures + golden tests each adapter must pass (idempotency, error semantics, retries, timeouts).
  - Add adapter registry + DI: select vendor per capability via env/feature flag.
  - Docs: `docs/PROVIDER_ABSTRACTION_SPEC.md`, `docs/VENDOR_CONFORMANCE_KIT.md`.
- **Endpoints:**
  - `GET /providers` (list loaded adapters + health), `POST /providers/reload` (hot-swap), `POST /providers/conformance/run`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase31_pal_conformance.py`
- **Expected Outcomes:**
  - Any adapter can be swapped with minimal blast radius.
- **Success Criteria:**
  - Conformance suite passes for at least one adapter per capability; hot-swap works at runtime.

---

## Phase 32 — Shadow Mode, Dual-Write & Traffic Switch
- [ ] **Goal:** Safely evaluate a new vendor in parallel and ramp via flags.
- **Key Changes:**
  - Dual-write (current + candidate) with read-compare and metrics diff.
  - Traffic ramp controller (5%→25%→50%→100%) via `ExperimentsProvider`.
  - Add kill-switch + rollback on SLO/ROAS regression.
  - Docs: add “Shadow/Ramp” section to `PROVIDER_ABSTRACTION_SPEC.md`.
- **Endpoints:**
  - `POST /providers/shadow/start`, `POST /providers/shadow/stop`, `POST /providers/ramp/{stage}`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase32_shadow_switch.py`
- **Expected Outcomes:**
  - Measured, reversible vendor switches.
- **Success Criteria:**
  - Shadow run produces comparison report; ramp completes without regressions; rollback restores baseline automatically on breach.

---

## Phase 33 — LLM Gateway & Policy Routing
- [ ] **Goal:** Abstract model vendors and route by policy (cost/latency/eval/safety).
- **Key Changes:**
  - Integrate a **gateway** (pluggable) behind `LLMGateway` interface.
  - Routing policy controlled by `models/policy.json` (weights, ceilings).
  - Evals loop: auto-retest prompts on model changes; prefer best scorer.
- **Endpoints:**
  - `POST /llm/route/test`, `GET /llm/models`, `POST /llm/policy/update`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase33_llm_gateway_routing.py`
- **Expected Outcomes:**
  - Model churn is low-risk; best-performing model used per task.
- **Success Criteria:**
  - Synthetic evals pick the same winner deterministically; fallbacks work on provider errors.

---

## Phase 34 — CDPProvider: Event/Identity Contracts & Profiles
- [ ] **Goal:** Warehouse-native profiles + predictive features, tool-agnostic.
- **Key Changes:**
  - `events.schema.json` + validators (`track/identify/alias/group`).
  - `CDPProvider` adapter (initial vendor of choice) with profile upsert, audience sync, traits/predictions fetch.
  - Identity graph reconciliation + consent flags.
  - Docs: `docs/DATA_CONTRACTS.md`.
- **Endpoints:**
  - `POST /cdp/events/ingest`, `POST /cdp/audiences/sync`, `GET /cdp/profile/{id}`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase34_cdp_contracts.py`
- **Expected Outcomes:**
  - Clean event data; unified profiles available to agents.
- **Success Criteria:**
  - Schemas validated in CI; profiles round-trip with deterministic merges.

---

## Phase 35 — ExperimentsProvider with Bandits (MAB/Contextual)
- [ ] **Goal:** Run bandits for creative & budget allocation; unify flags.
- **Key Changes:**
  - `ExperimentsProvider` supports: flags, A/B, Autotune bandits, contextual bandits hook.
  - Stopping rules & MDE calculators in `experiments/policy.json`.
  - Experiment artifacts: `ExperimentPlan.json`, `ExperimentReport.json`.
  - Docs: `docs/EXPERIMENT_POLICY.md`.
- **Endpoints:**
  - `POST /experiments/start`, `GET /experiments/{id}/report`, `POST /flags/ramp`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase35_experiments_bandits.py`
- **Expected Outcomes:**
  - Autonomous optimization within guardrails.
- **Success Criteria:**
  - Bandit converges on best variant in simulation; flags ramp per plan.

---

## Phase 36 — Metric Catalog & BI Agent v1 (AI-Analyst)
- [ ] **Goal:** Tool-agnostic KPI semantics + automated insights → roadmap.
- **Key Changes:**
  - `MetricCatalog.json` (activation, 7-day retention, CAC, LTV, ROAS).
  - BI agent generates `InsightReport.json` + `RoadmapSuggestions.json`.
  - Optional NLQ pass-through to analytics vendor, grounded on catalog.
  - Docs: `docs/METRIC_CATALOG.md`.
- **Endpoints:**
  - `GET /metrics/catalog`, `POST /bi/insights/run`, `POST /bi/suggestions/file`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase36_bi_insights_suggestions.py`
- **Expected Outcomes:**
  - Founder gets weekly insights and proposed backlog items.
- **Success Criteria:**
  - Insights link to data; suggestions create roadmap items with trace.

---

## Phase 37 — LifecycleProvider (Email/Push/In-App) + Compliance
- [ ] **Goal:** AI-assisted lifecycle campaigns with consent & policy guardrails.
- **Key Changes:**
  - `LifecycleProvider` adapter; consent/suppression enforcement.
  - Artifacts: `MarketingBrief.json`, `ChannelPlan.json`, `CreativeBatch.json`.
  - Pre-send checks (blocked terms, industry claims, rate limits).
  - Docs: `docs/MARKETING_BI_ARTIFACT_CONTRACTS.md`.
- **Endpoints:**
  - `POST /lifecycle/send`, `POST /lifecycle/sequence`, `POST /lifecycle/preview`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase37_lifecycle_compliance.py`
- **Expected Outcomes:**
  - Campaigns run within compliance + brand guardrails.
- **Success Criteria:**
  - Violations blocked with actionable errors; safe messages deliver.

---

## Phase 38 — AdsProvider (AI Campaign Types) + Budget Governor
- [ ] **Goal:** Use PMax/Adv+/Accelerate while your policy governs spend/safety.
- **Key Changes:**
  - `AdsProvider` supports: campaign create/pause/report; AI campaign types first-class.
  - Budget governor: 80% warn, 100% block, CPA/ROAS safety stops, daily pacing.
  - Artifact: `CampaignRun.json`; PR/cockpit budget tiles integrated.
- **Endpoints:**
  - `POST /ads/campaigns`, `POST /ads/{id}/pause`, `GET /ads/{id}/report`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase38_ads_guardrails.py`
- **Expected Outcomes:**
  - Safe autonomy for paid media at capped budgets.
- **Success Criteria:**
  - Guardrails trigger correctly; pause/kill-switches work deterministically.

---

## Phase 39 — Attribution v0 & Reverse-ETL Loop
- [ ] **Goal:** Close the loop: UTMs → attribution → audience sync back to tools.
- **Key Changes:**
  - `AttributionReport.json` (last-touch + sanity checks).
  - Reverse-ETL: `CDPProvider.syncAudience()` for “winners” → channels.
  - Seed lift test harness for future incremental experiments.
  - Docs: `docs/ATTRIBUTION_GUIDE.md`.
- **Endpoints:**
  - `POST /attribution/report/run`, `POST /audiences/sync`, `GET /audiences/status/{id}`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase39_attribution_reverse_etl.py`
- **Expected Outcomes:**
  - BI/Marketing agents act on measured impact, not guesses.
- **Success Criteria:**
  - Reports are reproducible; syncs are idempotent and audited.

---

## Phase 40 — LLM Observability & Evals as Gates
- [ ] **Goal:** Treat evals/trace metrics as merge/run gates (quality SLOs).
- **Key Changes:**
  - `LLMObservabilityProvider` adapters; trace IDs persisted with runs.
  - Eval datasets per blueprint; quality thresholds in CI (`eval/report.json`).
  - Vendor swap/ prompt changes require green evals.
- **Endpoints:**
  - `POST /evals/run`, `GET /evals/report`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase40_evals_gates.py`
- **Expected Outcomes:**
  - Measurable, enforced model & prompt quality over time.
- **Success Criteria:**
  - CI fails when eval score < threshold; traces link to runs & PRs.

---

## Phase 41 — VectorStore Abstraction & Memory Policy
- [ ] **Goal:** Swap vector stores and enforce provenance/safety for RAG.
- **Key Changes:**
  - `VectorStore` adapters (at least two vendors).
  - Memory policy: chunking, dedupe, provenance metadata, redaction.
  - RAG guardrails (domain allowlist, citation requirement).
- **Endpoints:**
  - `POST /memory/index`, `GET /memory/search`, `POST /memory/swap`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase41_vectorstore_swap.py`
- **Expected Outcomes:**
  - Reliable retrieval with clean swaps and auditable provenance.
- **Success Criteria:**
  - Search parity maintained after swap; citations attached to outputs.

---

## Phase 42 — Content Safety & Autonomy Controls (Creative + Spend)
- [ ] **Goal:** Enforce brand/policy moderation; cap autonomy by risk tier.
- **Key Changes:**
  - Creative moderation pre-checks (policy lists, classifier, and regex).
  - Autonomy levels per channel + per campaign risk; escalation path to Founder.
  - Spend policy: per-day and per-run caps; anomaly detectors.
- **Endpoints:**
  - `POST /safety/moderate`, `POST /autonomy/level/set`, `POST /budget/cap/set`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase42_content_policy.py`
- **Expected Outcomes:**
  - Zero “oops” creative or runaway spend; clear audit trail.
- **Success Criteria:**
  - Unsafe content blocked; anomaly triggers pause + alert; logs are redacted.

---

## Phase 43 — ROI-Driven Planning (Growth ←→ Roadmap)
- [ ] **Goal:** Use measured ROI to prioritize backlog autonomously.
- **Key Changes:**
  - BI agent merges `AttributionReport` + `ExperimentReport` into a Value Score per idea; opens/updates roadmap items automatically.
  - Cockpit card: “Top 5 ROI opportunities”.
- **Endpoints:**
  - `POST /planning/roi/score`, `POST /roadmap/suggest`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase43_roi_planning.py`
- **Expected Outcomes:**
  - Build/market loop self-prioritizes high-impact work.
- **Success Criteria:**
  - Suggestions created with traceable rationale; human can approve/merge.

---

## Phase 44 — SaaS Control Plane & Billing
- [ ] **Goal:** Monetize: usage metering, plans, and billing (founder-friendly).
- **Key Changes:**
  - Usage meters per tenant (tokens, runs, previews, storage).
  - Plan enforcement (community/hosted/enterprise).
  - Billing hook + invoices (mock driver locally).
  - Docs: `docs/BILLING_AND_PLANS.md`.
- **Endpoints:**
  - `GET /billing/usage`, `POST /billing/plan/set`, `POST /billing/invoice/mock`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase44_billing.py`
- **Expected Outcomes:**
  - Clear path to revenue without blocking community use.
- **Success Criteria:**
  - Over-limit actions are blocked or queued; invoices sum deterministically.

---

## Phase 45 — Enterprise Pack: SSO, RBAC, Audit Export
- [ ] **Goal:** Enterprise readiness for pilots (security + control).
- **Key Changes:**
  - SSO (OIDC/SAML) integration; role-based access with fine-grained scopes.
  - Audit export (JSON + CSV) for all privileged actions.
  - VPC/self-host guides.
  - Docs: `docs/ENTERPRISE_READINESS.md`.
- **Endpoints:**
  - `POST /auth/sso/config`, `GET /audit/export`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase45_enterprise.py`
- **Expected Outcomes:**
  - Comfortable enterprise adoption without custom code.
- **Success Criteria:**
  - RBAC enforced; SSO flows pass local fixtures; audit export is complete.

---

## Phase 46 — Founder Cockpit 2.0 (Growth & Insights)
- [ ] **Goal:** One pane for product + growth + finances, human-in-the-loop controls.
- **Key Changes:**
  - New tabs: Experiments, Campaigns, Audiences, ROI, Vendor Ramp.
  - One-click: Shadow start/stop, Ramp %, Kill-switch, Approve spend.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase46_cockpit_growth.py`
- **Expected Outcomes:**
  - Founder can guide the AI org from idea → deployed → growing.
- **Success Criteria:**
  - All actions available in UI; state reflects instantly and deterministically.
