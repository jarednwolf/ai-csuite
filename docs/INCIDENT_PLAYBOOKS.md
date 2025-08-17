# INCIDENT_PLAYBOOKS
_Last updated: 2025-08-17_

Standard playbooks for self‑work incidents: bisect, revert, shadow, ramp, rollback.

## 0) General Rules

- Always create an audit entry and an ADR for incidents.
- Prefer reversible actions; if irreversible, escalate to Founder (L0).
- Respect budgets and safety caps; pause self‑work if thresholds hit.

## 1) Revert (Fast Recovery)

**Trigger:** SLO breach, eval drop, safety violation, or budget overrun.

**Steps:**
1. Open incident: write audit row with reason and PR/commit refs.
2. Revert offending PR (git revert) into hotfix branch.
3. Run preview smoke + evals; ensure green.
4. Merge hotfix; update ADR with outcome; unpause when safe.

**Artifacts:**
- `incidents/revert-<id>.json` (reason, refs, results)
- ADR link in PR summary.

## 2) Bisect (Root Cause Isolation)

**Trigger:** Persistent regression with unclear culprit.

**Steps:**
1. Identify range of commits; run binary search in sandbox.
2. At each step: build, run smoke + evals; record metrics.
3. On culprit found: open fix PR referencing incident; include spec report.

**Artifacts:**
- `incidents/bisect-<id>.json`
- `self/spec_report.json` (for the fix PR)

## 3) Shadow (Vendor Candidate)

**Trigger:** Candidate adapter/model appears promising.

**Steps:**
1. `POST /providers/shadow/start` with capability + candidate.
2. Dual‑write metrics gathered; compare latency/error/cost.
3. If diff report is within policy bounds, propose ramp.

**Artifacts:**
- `provider_shadow_diffs/<id>.json` (sorted keys)

## 4) Ramp (Progressive Traffic)

**Trigger:** Shadow diff OK.

**Steps:**
1. Ramp stages: 5% → 25% → 50% → 100% via `POST /providers/ramp/{stage}`.
2. Monitor SLOs/ROAS; pause and rollback automatically on breach.
3. Promote to active at 100%; end shadow.

**Artifacts:**
- `ramp_reports/<id>.json`

## 5) Rollback (Anomaly Response)

**Trigger:** Any anomaly during canary or ramp.

**Steps:**
1. Pause capability and revert traffic to baseline.
2. File incident; capture diffs; notify Founder if high/critical.
3. Open fix PR; include plan to re‑shadow if needed.

**Artifacts:**
- `incidents/rollback-<id>.json`

## Communication

- Cockpit shows incident tiles; PR summary includes status and links.
- Founder notified only on High/Critical or repeated Medium incidents.

## Determinism

- All reports: sorted keys, newline‑terminated; seeds recorded when sampling.

## API Mappings (Phase 60)

- Revert: `POST /incidents/revert` → writes `apps/orchestrator/orchestrator/incidents/revert-<id>.json`
- Bisect: `POST /incidents/bisect` → writes `apps/orchestrator/orchestrator/incidents/bisect-<id>.json`
