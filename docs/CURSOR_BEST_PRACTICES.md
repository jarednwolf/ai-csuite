AI-CSuite — Cursor Operating Guide & Dev Standards

Last updated: 2025-08-15

Purpose. This guide tells Cursor (and any AI pair-programmer) exactly how to work inside the AI-CSuite repo so we follow the Phases tracker, produce typed artifacts, and meet strict development standards every time.

Related docs:

Handoff & Bootstrap: docs/AI-CSUITE_HANDOFF.md

Agent Operations: docs/AGENT_OPERATING_MANUAL.md

Phase Tracking Checklist (Phases 1–16): docs/PHASE_TRACKING_CHECKLIST.md

0) Quick Start — How Cursor Should Use These Docs

Ground yourself first (mandatory):

Read docs/AI-CSUITE_HANDOFF.md to understand the stack, scripts, env, and flows.

Read docs/AGENT_OPERATING_MANUAL.md to understand the workings of the agents and how we want decisions and development to progress.

Read docs/PHASE_TRACKING_CHECKLIST.md to know which phase we’re on and what to deliver. We are currently at Phase 11 (LangGraph persistence + resume) with local tests green.

Work only in small, reversible steps aligned to the current phase.

Always output changes as atomic patch blocks (see §4) with matching tests. No ad-hoc instructions or partial diffs.

Enforce typed artifacts & gates (PRD/Design/Research/Plan/QA; DoR/DoD). If a gate isn’t met, stop and fix before proceeding.

Use scripts to validate locally:

./scripts/rebuild_env.sh, ./scripts/dev_doctor.sh, ./scripts/test_local.sh

Update the tracker (docs/PHASE_TRACKING_CHECKLIST.md) when a phase or item is completed.

Rule of thumb: If a change isn’t testable or doesn’t move the active phase forward, don’t ship it.

1) Cursor Working Agreement (non-negotiable)

✅ Follow contracts over chat. Every step produces a typed artifact (JSON) or a tested code patch.

✅ Evidence first. Cite KB or repo evidence in PRD/Design/Research; cite diffs/tests for ENG/QA.

✅ Idempotent patches. Re-applying the same patch should not corrupt state.

✅ Security & secrets. Never commit secrets. Use env vars; keep PAT scopes minimal.

✅ Repro or it didn’t happen. All changes must be verifiable via scripts/tests.

2) Standard Workflow (Cursor Checklists)
A) Pre-work (before editing)

 Confirm current phase in docs/PHASE_TRACKING_CHECKLIST.md.

 Ensure local env is correct: ./scripts/dev_doctor.sh.

 If touching delivery flow, ensure DoR is satisfied (PRD/Design/Research present & valid).

 Create/update ADR if you’re making a meaningful decision (see §7 templates).

B) Implement (small, reversible)

 Create a single patch block per file changed (see §4 format).

 Add/modify tests first (TDD preferred).

 Keep PRs small; follow branch naming feature/<roadmap_id>-<slug>.

C) Validate

 Run ./scripts/test_local.sh and ensure green.

 For GH paths, ensure dry-run or live tests as appropriate (see handoff doc).

D) Prepare PR (orchestrator-aware)

 Ensure statuses will pass: ai-csuite/dor, ai-csuite/human-approval, ai-csuite/artifacts.

 Upsert the PR summary comment (orchestrator will do this; ensure inputs are present).

 Reference ADRs & artifacts in PR description.

E) Track & Close

 Tick relevant items in docs/PHASE_TRACKING_CHECKLIST.md.

 If finishing a phase, mark it [x] and link to commits/PRs.

 Ingest learnings into KB where applicable.

3) Cursor Prompt Playbooks (copy/paste)
3.1 Feature Slice (phase-aligned)
Act as an AI engineer working in the AI-CSuite repo.

Goal: Implement the smallest viable change for Phase <N>: <short objective>.
Grounding:
- Read ./docs/AI-CSUITE_HANDOFF.md and ./docs/PHASE_TRACKING_CHECKLIST.md
- Enforce DoR/DoD and typed artifacts from the Agent Operating Manual.

Output constraints:
1) Only produce patch blocks (one per file), COMPLETE file contents.
2) Include tests (pytest) and, if needed, update ./scripts/test_local.sh.
3) No secrets; respect Python 3.12.5; FastAPI + Pydantic patterns.
4) After code, add a brief note: which checklist items to check off.

Deliverables:
- Code changes
- Tests
- Minimal docs updates (if any)

3.2 Bug Fix
Context: A failing test or defect <describe>.
Task: Produce a surgical fix with a reproducible test.

Requirements:
- Add/extend a test that fails before the fix and passes after.
- Include defensive checks and logging if the bug relates to state transitions.
- Maintain idempotency and API compatibility.

Output: Patch blocks only (complete files), including tests.

3.3 Refactor (no behavior change)
Task: Improve structure/readability/perf without changing behavior.

Guardrails:
- No public API changes unless documented and approved.
- Tests: expand coverage to prove behavior is unchanged.
- Update docs if interfaces are clarified.

Output: Patch blocks only, with tests.

3.4 Test/Validation Only
Task: Increase coverage for <module> and validate Phase <N> invariants.

Output: Tests + any harmless test fixtures; no runtime code changes unless a defect is found.

4) Patch Block Format (strict)

One file per block, complete file content.

Use the exact header:

=== PATCH: <relative/path/from/repo/root> ===
<complete file content>


Tests must be runnable via ./scripts/test_local.sh.

If tests depend on env, add instructions or safe defaults in the handoff doc.

5) Development Standards
5.1 Python & Runtime

Python 3.12.5 fixed; no 3.13 (NumPy issues noted).

Use type hints everywhere; mypy-friendly.

Prefer dataclasses/Pydantic models for contracts; validate at boundaries.

5.2 FastAPI / API Design

Clear 2xx/4xx/5xx semantics; raise HTTPException with detail codes.

Idempotent POSTs where practical; GETs side-effect free.

Pydantic models as request/response schemas; include example payloads.

5.3 Persistence

SQLAlchemy for models; migrations scripted.

Avoid destructive migrations; include safe up/down notes if needed.

5.4 Testing

pytest: unit + integration.

Name tests by phase when helpful: test_phase<N>_<area>_*.py.

Ensure artifacts (PRD/Design/Research/Plan/QA) have validator tests.

5.5 Linting & Style

Black/ruff (or flake8) style; docstrings for public functions.

No long functions (>50–80 lines) without justification.

Log with structure (key=value) at decision points and failures.

5.6 Security

No secrets in code/tests. .env for local; CI uses secret store.

Respect principle of least privilege (PAT scopes).

Input validation & output encoding; avoid unsafe eval/exec.

5.7 Reliability

Retries with backoff for network calls; timeouts everywhere.

Deterministic resume: store state transitions; never swallow exceptions.

6) Phase Compliance (what Cursor must check)

Cursor should read and update docs/PHASE_TRACKING_CHECKLIST.md as a source of truth.

Phase 1–3: CRUD and Discovery endpoints exist with tests; PRD validator present.

Phase 4–5: Design/Research validators; KB ingestion/search integrated and cited.

Phase 6–7: GitHub PR create; statuses posted; approval/merge endpoints.

Phase 8–9: Webhooks processed; PR summary comment upserted (single canonical).

Phase 10–11: LangGraph pipeline and Temporal durability; resume from last good step.

Phase 12+: Multi-persona agents, richer KB, telemetry, guardrails, cockpit UI.

If any prerequisite for the active phase is missing, backfill first with a minimal patch + tests.

7) Templates (Cursor may insert as needed)
7.1 ADR (drop in docs/adr/ADR-<run>-<slug>.md)
# ADR: <Decision Name>
- **Run**: <id> / **Item**: <id>
- **Date**: YYYY-MM-DD
- **Context**: (1–3 sentences)
- **Options**: (A/B/C with pros/cons)
- **Decision**: (Chosen option + rationale)
- **Owner**: (role)
- **Review Date**: (if two-way door)
- **Links**: PR, artifacts, KB refs

7.2 PR Description (for orchestrator/maintainers)
## Summary
<what changed and why>

## Artifacts
- PRD: <path or link>
- DesignReview: <path>
- ResearchSummary: <path>
- TechPlan: <path>
- QAReport (if applicable): <path>

## Statuses & Gates
- ai-csuite/dor: <pending|success>
- ai-csuite/human-approval: <pending|success>
- ai-csuite/artifacts: <pending|success>

## Tests
- Local: ./scripts/test_local.sh → green
- (Optional) Live: pytest -m requires_github → <result>

## Risk / Rollback
<impact, fallback, feature flags>

8) “Stop Signs” — when Cursor must not proceed

 DoR not satisfied (missing PRD/Design/Research or failing validation).

 No tests for a change that impacts runtime behavior.

 GH statuses can’t be set or read (token/permissions issue).

 Secrets would be hardcoded or leaked in logs.

 A change is a one-way door without ADR + explicit approval.

If any stop sign is true, produce a minimal fixing patch (or an ADR) first.

9) How Cursor Updates the Tracker

After delivering a change:

 Edit docs/PHASE_TRACKING_CHECKLIST.md:

Mark the relevant phase item(s) as [x].

Add a short bullet with the PR link / commit hash and test evidence.

 If a phase completes, mark the phase header [x].

 If a new sub-task is discovered, add it under the phase with [ ] and a one-line description.

10) Example: Minimal, Compliant Delivery
=== PATCH: apps/orchestrator/orchestrator/example_module.py ===
<complete file content showing a small, reversible change with types and logging>

=== PATCH: apps/orchestrator/tests/test_example_module.py ===
<complete tests that fail before and pass after>

=== PATCH: docs/PHASE_TRACKING_CHECKLIST.md ===
<toggle [ ] -> [x] for the relevant item; add a one-line result link>


Run locally:

./scripts/dev_doctor.sh
./scripts/test_local.sh
# (optional) export GITHUB_TOKEN=... && pytest -m requires_github -q

11) Operating Rituals (for Cursor & humans)

Kickoff Sync: Confirm success metric, scope edges, risks, autonomy level.

Design Critique: Brief DL↔HP pass; update PRD/DesignReview as needed.

Risk Review: RL↔CTO review assumptions & mitigation; update TechPlan.

Change Review: If ENG deviation >20% or security impact, raise ADR.

Shiproom: QA presents QAReport; if all green → approve & merge.

Each ritual outputs notes or an ADR. Cursor should prompt for the missing artifact if not found.

12) Common Pitfalls (and how Cursor avoids them)

Drift in Python version → Always patch .python-version, Dockerfile, workflows to 3.12.5 when needed.

Forgotten PR summary → Call the orchestrator comment refresh endpoint or ensure inputs exist.

Incomplete tests → Add both positive and negative cases; cover error paths and idempotency.

Webhook flakiness → Document SMEE URL & WEBHOOK_SECRET; add retry/backoff and logging.

13) Responsibility Matrix (Cursor view)
Role	Cursor Responsibilities
CoS	Ensure gates, owners, and autonomy level; update tracker; schedule rituals (notes/ADR).
HP	Maintain PRD.json; keep AC & metrics crisp; update after critiques.
DL	Maintain DesignReview.json; heuristics score ≥ 80; a11y notes present.
RL	Maintain ResearchSummary.json with citations & confidence.
CTO	Maintain TechPlan.json; architecture & tasks; risk/security controls.
ENG	Implement; keep diffs small; link commits to tasks; trigger Change Review when needed.
QA	Write QAReport.json; gate DoD; loop with ENG up to bounded retries.

Cursor may “play” any role, but must adhere to the artifact contracts and update the tracker.