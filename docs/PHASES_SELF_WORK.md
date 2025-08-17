# AI-CSuite — Self-Work Roadmap (Phases 47–63)

_Last updated: 2025-08-16_

This document tracks the phases required for **AI-CSuite to begin working on itself** — from repo intelligence to self-healing and ROI-driven autoprioritization.  
Each phase contains: **Goal**, **Key Changes**, **Tests**, **Expected Outcomes**, and **Success Criteria**.  
Mark `[x]` when complete.

---

## Phase 47 — Repo Intelligence & Intent Graph
- [x] **Goal:** Give agents a precise map of the codebase to reason about changes safely.
- **Key Changes:**
  - AST + symbol indexer for Python/TypeScript; ownership map (which module “owns” which behavior).
  - Cross-refs for tests ↔ code; detect orphaned modules and low-coverage areas.
  - API: `GET /repo/map`, `GET /repo/ownership`, `GET /repo/hotspots`.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase47_repo_map.py`
- **Expected Outcomes:** Deterministic repo map available to agents; stable IDs for symbols/paths.
- **Success Criteria:** Index is reproducible; queries resolve symbols and owning tests deterministically.

---

## Phase 48 — Contract Coverage & Gap Detector
- [x] **Goal:** Quantify how well PRD/TechPlan/DoR/DoD + policies are reflected in code/tests.
- **Key Changes:**
  - Compute “contract coverage” (schemas validated, gates present, tests exist).
  - Report gaps with fix suggestions (missing validators, missing tests).
  - API: `POST /quality/contracts/report` → `quality/contracts_report.json`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase48_contract_coverage.py`
- **Expected Outcomes:** Machine-readable gap list per module/run.
- **Success Criteria:** Report stable across runs; false-positive rate under threshold.

---

## Phase 49 — Self-PR (Docs & Checklists Only)
- [x] **Goal:** Safely start self-work with docs/checklists/markdown.
- **Key Changes:**
  - Agent generates patches to `.md` / `docs/` / `scripts/*.sh --help` only.
  - Opens PRs with ADR + preview diff; statuses: `ai-csuite/self-docs`.
  - API: `POST /self/pr/docs`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase49_self_docs_pr.py`
- **Expected Outcomes:** Routine doc improvements shipped by agents.
- **Success Criteria:** PRs pass markdown lint + link checks; deterministic diffs; human approval required.

---

## Phase 50 — Test Synthesis & Guard Scaffolding
- [x] **Goal:** Agents generate unit/integration tests from artifacts + repo map.
- **Key Changes:**
  - Test templates per capability (providers/routers/services).
  - Code-to-test generator (deterministic prompts + fixtures).
  - API: `POST /self/tests/suggest` → PR with tests only.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase50_test_synthesis.py`
- **Expected Outcomes:** Coverage increases without touching production logic.
- **Success Criteria:** Coverage delta ≥ configured target; no flaky tests.

---

## Phase 51 — Speculative Execution & Preview Safety Net
- [x] **Goal:** Run candidate patches in a sandbox to predict side effects.
- **Key Changes:**
  - “Speculative” containers with seeded data; run smoke + eval suites.
  - Capture perf/cost metrics; publish preview report to PR summary.
  - API: `POST /self/speculate` → `self/spec_report.json`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase51_speculative_exec.py`
- **Expected Outcomes:** Risk classification per patch before review.
- **Success Criteria:** Spec reports deterministic; previews gated by green smoke.

---

## Phase 52 — Cross-Agent Change Review (CTO/ENG/QA) & ADR Bot
- [x] **Goal:** Institutionalize agent code review + ADR creation.
- **Key Changes:**
  - Multi-agent review ritual → “Steelman → Options → Decision → Owner”.
  - ADR auto-filed with links to diffs, tests, spec report.
  - Status: `ai-csuite/self-review`.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase52_agent_review_adr.py`
- **Expected Outcomes:** Consistent, auditable agent reviews.
- **Success Criteria:** ADRs present for all self-PRs; no merge without review.

---

## Phase 53 — Low-Risk Code Autofixes (Auto-Merge Allowed)
- [ ] **Goal:** Let agents auto-land mechanical changes with guarantees.
- **Key Changes:**
  - Linters/formatters/type fixes; dead-code removal; comment updates.
  - Policy: auto-merge if (tests + spec + evals + safety) are green.
  - Status: `ai-csuite/self-lowrisk`.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase53_lowrisk_automerge.py`
- **Expected Outcomes:** Reduced toil; higher code health.
- **Success Criteria:** Zero production behavior deltas in simulation; rollbacks unused.

---

## Phase 54 — Provider Adapter Scaffolding via Conformance Kit
- [x] **Goal:** Agents add/upgrade adapters using PAL + conformance.
- **Key Changes:**
  - From a `providers.yaml` delta, scaffold adapter + tests + docs.
  - Run conformance + shadow start automatically (disabled in CI).
  - API: `POST /self/providers/scaffold`
- **Tests:**  
  - `apps/orchestrator/tests/test_phase54_adapter_scaffold.py`
- **Expected Outcomes:** Faster vendor on-ramp with low risk.
- **Success Criteria:** New adapters pass conformance and boot in shadow mode.

---

## Phase 55 — Dependency & Supply-Chain Upgrader
- [x] **Goal:** Keep deps fresh with SBOM/licensing and safety gates.
- **Key Changes:**
  - Proposal bot bumps pinned versions, regenerates SBOM, re-runs SAST.
  - Merge policy: only if CI/evals/safety green + policy allowlist.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase55_deps_supplychain.py`
- **Expected Outcomes:** Secure, reproducible upgrades.
- **Success Criteria:** No license/regression violations; changelog updated.

---

## Phase 56 — Blueprint Library Auto-Expansion
- [x] **Goal:** Agents add new blueprints (e.g., video avatar tutoring, home connectivity, food ordering) from specs.
- **Key Changes:**
  - From `blueprints/*.json` spec, scaffold repo/app + tests + preview.
  - Ensure artifacts: PRD/Design/TechPlan/QAReport present and valid.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase56_blueprint_autogen.py`
- **Expected Outcomes:** App Factory grows without human toil.
- **Success Criteria:** New blueprints pass validators + preview smoke.

---

## Phase 57 — Self-Change Feature Flags & Canary Rollout
- [x] **Goal:** Roll out agent-made changes with progressive delivery.
- **Key Changes:**
  - Feature flags wrap self-changes; canary % controlled via ExperimentsProvider.
  - Auto-rollback on regressions (evals/safety/latency).
- **Tests:**  
  - `apps/orchestrator/tests/test_phase57_self_canary.py`
- **Expected Outcomes:** Safe production trials of agent patches.
- **Success Criteria:** Canary ramps to 100% only on green guardrails.

---

## Phase 58 — Evals/Regression Protectors for Self-Changes
- [x] **Goal:** Treat evals as hard gates for any self-PR.
- **Key Changes:**
  - Baseline eval suite for orchestrator endpoints & agent prompts.
  - Prevent merge if eval score < threshold; store diff vs. baseline.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase58_self_eval_gates.py`
- **Expected Outcomes:** Quality preserved as code evolves.
- **Success Criteria:** No merges below threshold; eval history linked to PR.

---

## Phase 54–56 — Developer Productivity Extensions

- Provider Adapter Scaffold (Phase 54):
  - `POST /self/providers/scaffold` → generate adapter skeletons and run local conformance. Idempotent; outputs in `apps/orchestrator/orchestrator/providers/adapters/` and `apps/orchestrator/orchestrator/reports/conformance/`.
- Supply‑Chain Upgrader (Phase 55):
  - `orchestrator/supply_chain/upgrader.py` proposes minor/patch bumps from an offline catalog and writes `apps/orchestrator/orchestrator/reports/supply_chain/proposal.json`.
- Blueprint Auto‑Expansion (Phase 56):
  - `POST /self/blueprints/scaffold` → scaffold from registry manifests; safe in CI.

---

## Phase 59 — Cost/Performance Optimizer Agent
- [x] **Goal:** Autonomously cut latency and $ without behavior change.
- **Key Changes:**
  - Identify hot paths; propose caching/async/model routing tweaks.
  - Cost ledger deltas surface in PR summary; rollback on SLO breach.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase59_cost_perf_optimizer.py`
- **Expected Outcomes:** Lower p95 and lower run-costs.
- **Success Criteria:** Measurable improvements with unchanged outputs.

---

## Phase 60 — Self-Healing: Auto-Revert & Bisection
- [x] **Goal:** When a self-change regresses, recover automatically.
- **Key Changes:**
  - On alert: revert PR, bisect culprit commits in sandbox, open fix PR.
  - ADR for incident; KB ingest of postmortem.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase60_self_healing.py`
- **Expected Outcomes:** Minimal MTTR without human paging.
- **Success Criteria:** Revert & bisect flows deterministic and logged.

---

## Phase 61 — Auto-Vendor Swap Pipeline (Shadow → Ramp)
- [x] **Goal:** Agents initiate vendor upgrades when metrics warrant it.
- **Key Changes:**
  - Detect better AI-native vendor/model; run shadow (Phase 32), analyze diffs, propose ramp with budget/safety caps.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase61_vendor_swap.py`
- **Expected Outcomes:** Continual improvement with low risk.
- **Success Criteria:** Successful ramps with no SLO/ROAS regression.

---

## Phase 62 — ROI-Aware Roadmap Autoprioritizer v2
- [ ] **Goal:** Use Value Score + cost/complexity + learning value to prioritize self-work.
- **Key Changes:**
  - Planner merges BI insights, attribution, eval gaps, and cost hotspots to open/sequence roadmap items.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase62_roi_prioritizer.py`
- **Expected Outcomes:** Highest ROI self-tasks tackled first.
- **Success Criteria:** Backlog updated; founder can accept/override.

---

## Phase 63 — Founder Copilot for Self-Work
- [ ] **Goal:** Human-in-the-loop steering with crisp controls.
- **Key Changes:**
  - Cockpit: Approve/deny classes of self-changes; set autonomy levels; budget limits; vendor preferences.
- **Tests:**  
  - `apps/orchestrator/tests/test_phase63_copilot_controls.py`
- **Expected Outcomes:** Founder guides the AI org with one pane.
- **Success Criteria:** All controls deterministic; audit trail complete.
