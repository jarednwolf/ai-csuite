AI‑CSuite — Production Readiness Checklist

Last updated: 2025‑08‑15

This checklist hardens AI‑CSuite for autonomous app delivery from roadmap → deployed while preserving typed‑artifact gates and ADR‑backed decisions. Use it before enabling L1 autonomy for a run. See also: Agent Operating Manual, Gates & Policies (DoR/DoD)
; Phase 11–16 APIs & UI
; Cursor Dev Standards
.

1) Service SLOs & Runbooks

 Define SLOs: API availability ≥ 99.9%, queue latency p95 < 2s, step retry success ≥ 99%.

 Alerts: on SLO burn rate, retry‑exhaust, PR gating stuck > 30m, cost over budget.
 
 Postmortems: automated artifact per run; redacted summary ingested to KB (Phase 30).
 Runbooks: webhook failures, GitHub 403/abuse‑limit, graph retry loops, deployment rollback.

 On‑call doc: escalation triggers mirror the Operating Manual (blocked > 24h; one‑way doors).

2) Safety & Governance

 DoR/DoD enforced at API & CI: block merges if contracts invalid or statuses not green.

 Secrets: no plaintext; scanners enabled; PAT scopes minimal; env var maps per environment.
 Compliance hardening (Phase 23): local secrets scanner & deterministic reports; PII/PHI redaction filters in logs/prompts; append-only audit logs for sensitive events.

 Prompt & log hygiene: mask PII/PHI; redact secrets; sampling toggle for debug logs.

 Policy‑as‑Code: approve only if policy bundle passes (e.g., ADR present for one‑way door).

3) Reliability & Determinism

 Idempotent activities; de‑dup keys per step (run_id, step_name).

 Backoff (tracked deterministically; jitter disabled in offline phases); max attempts 3; surface error chains in /graph/history. Partner adapters (Phase 29) enforce idempotency keys, retry/backoff counters, rate-limit token bucket, and circuit‑breaker with reset API.

 Pause/Resume semantics validated; resume deterministically from persisted state.

 Disaster recovery: DB backups nightly; restore test run monthly.

  Scheduler & Scale (Phase 28): deterministic, offline scheduler with priorities and quotas. Concurrency governed by `SCHED_CONCURRENCY`; per‑tenant caps via `SCHED_TENANT_MAX_ACTIVE`; backpressure at `SCHED_QUEUE_MAX`. Cockpit page `/ui/scheduler` exposes state and a manual Step.

4) Supply Chain & Build Integrity

 Lockfiles (pip‑tools); pinned base images; SBOM + license scan in CI.

 Reproducible builds: deterministic versions across Dockerfile, workflows, .python-version (3.12.5).

 Dependency bot (batch PRs weekly); security advisories triage runbook.

5) Observability & Cost

 Traces/spans per graph node; attributes: run_id, persona, tokens_in/out, latency, retries.（Phase 14 baseline）

 Cost meter: per‑run & per‑persona totals; add to PR summary comment + cockpit.

 Dashboards: SLOs, error budget, retry rates, webhook throughput, PR gate durations.

6) Deployment & Environments

 IaC modules: staging/prod (DB, cache, secrets, compute, domains).

 Preview envs per PR with seeded data; smoke tests must pass before merge.
 
 Phase 18 baseline:
 
 - Simulated preview URL per branch via PREVIEW_BASE_URL (default `http://preview.local`).
 - Status gate `ai-csuite/preview-smoke` transitions: pending → success/failure.
 - Dry‑run supported (GITHUB_WRITE_ENABLED=0): no external writes; statuses/comments simulated; ledger still recorded.

 Progressive delivery: feature flags, canary; rollback recipe & checklist.

 Data migrations playbook (pre‑checks, backup, post‑checks).

6.1) Deterministic IaC & Rollout Gating (Phase 25)

 Local-only, deterministic artifacts and checks:
 - IaC plan/apply simulator:
   - `scripts/iac_plan.py` → `iac/plan.json`
   - `scripts/iac_apply.py` → `iac/state.json`
 - Progressive delivery harness:
   - `scripts/release_run.py` → `deployments/report.json`
   - `scripts/release_history.py` → `deployments/history.json`
 - CI wrapper: `scripts/release_check.sh` fails on threshold violations (unless override added later)

 Requirements:
 - No network; curated JSON manifests/fixtures only
 - Stable ordering; sorted-keys JSON; newline-terminated
 - Idempotent reruns yield identical outputs
 - Optional KB ingestion of redacted release summaries when `RELEASE_WRITE_KB=1` (offline only)

7) App Factory Integration

 Blueprint registry versioned; manifests validated at DoR.（See APP_FACTORY_BLUEPRINTS.md）

 Scaffolder can create new repo OR branch in existing repo.

 Default blueprints ship with CI, IaC, auth, seed data, e2e tests.

 Quality gates per blueprint: a11y ≥ 80, e2e coverage ≥ 70%, performance budget.

  Phase 26 artifacts:
  - Deterministic blueprint gates report: `scripts/blueprints_report.py` → `blueprints/report.json` (sorted keys, newline-terminated; timestamps reused when unchanged)
  - Wrapper `scripts/blueprints_check.sh` for local/CI; exits non‑zero on manifest errors or gate violations

8) Evaluation & Learning

 Golden task suites per app type (CRUD, payments, media, realtime).

 Nightly eval; trend charts; regression alerts.
 
 Deterministic local harness available:
 
 - `scripts/eval_run.py` and `scripts/eval_history.py` produce `eval/report.json` and `eval/history.json` with stable ordering and newline termination.
 - CI wrapper `scripts/eval_check.sh` enforces per-suite threshold gating.

 KB ingestion of postmortems/ADRs; artifacts cite KB evidence.

9) Cockpit & Human‑in‑the‑loop

 Cockpit shows statuses, history, metrics, costs; approve/merge actions; create-from-blueprint flow and budget compute controls (local-only, deterministic). Postmortems page lists generated artifacts and supports Generate/Ingest controls (Phase 30).

 PR summary comment upsert verified (single canonical).

 Autonomy level per run (L0/L1) visible; escalation button to Founder.

 Go/No‑Go Gate: All checks above for target environment are green.