AI-CSuite — Agent Operating Manual

Purpose: Define how our LLM-backed “C-suite” collaborates to ship features safely and fast. This doc encodes the sequential workflow, conversation rituals that improve quality, typed artifacts for handoffs, and gates (DoR/DoD) that keep us honest.

Roles (personas): Chief of Staff (CoS), Head of Product (HP), Design Lead (DL), Research Lead (RL), CTO (architecture & plan), Engineer (ENG), QA.
Orchestrator: runs the graph, persists state, enforces contracts & gates, touches GitHub.

1) Golden Rules

Contracts over chat: Every step outputs a typed artifact (JSON) that the Orchestrator validates before moving on.

Evidence first: Product, Design, and Research must cite KB or data; QA cites tests/logs; ENG cites diff/branch.

Talk when it matters: We convene short, structured conversations at decision forks (listed below) and then record an ADR.

Small reversible steps: Prefer “two-way doors” (reversible). Escalate “one-way doors” to Founder via CoS.

Fail loudly, retry sanely: Automatic retries (bounded) + clear escalation paths.

2) End-to-End Flow (Swimlane)
CoS   →   HP   →   DL   →   RL   →   CTO   →   ENG   →   QA   →   CoS
 |        |        |        |        |        |        |        |
 kickoff  PRD   design   research   plan     code      tests    ship/update
         (DoR) heuristic  summary   + tasks  + PR      report   roadmap


High-level steps

Kickoff (CoS)

Inputs: Roadmap item.

Output: Run initialized, timeline, owners, autonomy level.

Conversation point: Scope & success alignment (Founder optional).

Product PRD (HP)

Output: PRD.json (contract below).

DoR Gate starts here (completeness & quality).

Design Review (DL)

Output: DesignReview.json (heuristics score + a11y notes).

Conversation point: UX critique (HP+DL short debate).

Research Summary (RL)

Output: ResearchSummary.json (citations to KB/data).

Conversation point: Assumption risk check.

Technical Plan (CTO)

Output: TechPlan.json (arch decisions, tasks, risk controls).

Conversation point: Trade-offs & risk mitigation.

Implementation (ENG)

Output: PR (+ commit of artifacts); Orchestrator sets statuses, upserts PR summary comment.

Conversation point: If blocked or large deviation from plan → CTO consult.

Verification (QA)

Output: QAReport.json (test results, defects); loop with ENG if needed (bounded).

DoD Gate enforced here.

Close & Update (CoS)

Output: Run summary, roadmap updated, PR merged (if green), KB ingested with learnings.

3) Conversation Rituals (Where “talk” beats “do”)

Short, time-boxed sessions. CoS schedules, captures notes, and files ADR.

Kickoff Sync (10–15 min)

Agenda: success metric, scope edges, risks, autonomy level.

Output: ADR ADR-<run>-kickoff.md.

Design Critique (10 min)

HP & DL review PRD vs DesignReview.

Output: notes → PRD update or Design tweak (tracked in ADR).

Risk Review (10 min)

RL & CTO validate assumptions and risk mitigations.

Output: TechPlan updates + Research citations.

Change Review (on deviation)

If ENG proposes deviation > 20% effort or security impact → meet.

Output: ADR with decision, PR updated.

Shiproom (2–5 min)

QA presents QAReport. All statuses green? CoS triggers approval & merge.

Debate style: “Steelman → Options → Decision → Owner → Review date.” Record in ADR.

4) Handoff Contracts (Typed Artifacts)

All artifacts are JSON stored with the run. Minimal but explicit.

4.1 PRD.json
{
  "title": "string",
  "problem": "string",
  "user_stories": [{"as_a": "string", "i_want": "string", "so_that": "string"}],
  "acceptance_criteria": [{"id": "AC-1", "given": "string", "when": "string", "then": "string"}],
  "metrics": [{"name": "string", "target": "string"}],
  "risks": [{"risk": "string", "mitigation": "string"}],
  "references": ["KB:... or URL..."]
}

4.2 DesignReview.json
{
  "passes": true,
  "heuristics_score": 0,
  "a11y_notes": "string",
  "references": ["KB:... or URL..."]
}

4.3 ResearchSummary.json
{
  "summary": "string",
  "evidence": ["KB:... or URL..."],
  "confidence": "low|medium|high"
}

4.4 TechPlan.json
{
  "architecture": "string (high-level diagram/desc)",
  "tasks": [{"id": "T-1", "desc": "string", "owner": "ENG", "estimate": "1d"}],
  "risks": [{"risk": "string", "mitigation": "string"}],
  "security": [{"item": "string", "control": "string"}],
  "branch": "feature/<roadmap_id>-<slug>"
}

4.5 QAReport.json
{
  "test_results": [{"name": "string", "status": "pass|fail", "details": "string"}],
  "defects": [{"id": "D-1", "desc": "string", "severity": "minor|major|critical"}],
  "recommendation": "proceed|block|retest"
}

5) Gates & Policies
5.1 Definition of Ready (DoR)

PRD: title, problem, ≥1 user story, ≥1 AC, ≥1 metric, ≥1 risk+mitigation.

Design: heuristics_score ≥ 80, a11y notes present.

Research: summary + ≥1 citation.

Alignment: no contradictions between PRD/Design/Research.

Owner: CoS records owners and autonomy level.

Orchestrator blocks delivery until DoR passes.

5.2 Definition of Done (DoD)

Tests green (unit/integration as applicable).

Artifacts committed (PR summary comment updated).

GitHub statuses: ai-csuite/dor=success, ai-csuite/human-approval=success, ai-csuite/artifacts=success.

QA recommendation = proceed.

PR merged; roadmap updated; KB ingested with learnings.

Postmortem & Learning Loop (Phase 30)

- After merge or run completion, generate a deterministic postmortem artifact summarizing: status, timeline, retries, failed steps, alerts, budget, causes, learnings, and action items.
- Ingest a short, strictly redacted summary paragraph into the local KB (`postmortem` kind) to close the loop for future retrieval by Product/Research.
- Minimal audit events are recorded (actor=api) for generation/reset/ingest with redacted details.

6) Failure Handling & Loops

Retries: Exponential backoff, max 3 per failing step. For partner adapters (Phase 29), retries/backoff are tracked deterministically without sleeping; idempotency keys avoid duplicate work; rate‑limits and circuit‑breakers are enforced locally and reset via API.

QA↔ENG loop: max_qa_loops (default 3). Each loop appends a defect item.

Escalation triggers (CoS):

Expected effort ↑ > 20%,

P0 security/regression risk,

Blocked > 24h,

Model cost threshold exceeded.

7) Autonomy Levels (RACI-lite)
Level	What agents can do without Founder	When to escalate
L1	Full cycle per this manual	One-way doors, scope/effort +20%, security/cost risks
L0	Prepare artifacts only	Any code/infra change

CoS controls level per run.

8) Decision Records (ADR template)

File: docs/adr/ADR-<run>-<slug>.md

# ADR: <Decision Name>
- **Run**: <id> / **Item**: <id>
- **Date**: YYYY-MM-DD
- **Context**: (1–3 sentences)
- **Options**: (A/B/C with pros/cons)
- **Decision**: (Chosen option + rationale)
- **Owner**: (role)
- **Review Date**: (if two-way door)
- **Links**: PR, artifacts, KB refs

9) Persona Prompts (system-style summaries)

Use these as foundation prompts (each can be extended with project context).

Chief of Staff (CoS)

Coordinate the run. Maintain timeline, owners, autonomy level. Schedule conversation rituals. Ensure gates are enforced. Summarize decisions (ADR), update roadmap, and notify Founder only on escalation triggers.

Head of Product (HP)

Produce a minimal PRD tied to measurable outcomes. Cite KB. Optimize for clarity and smallest viable slice. Update PRD after critiques/decisions.

Design Lead (DL)

Evaluate against Nielsen heuristics and a11y. Propose low-effort UX improvements. Provide a score and notes. Flag risks that change behavior/AC.

Research Lead (RL)

Validate assumptions with KB/evidence. Identify unknowns. Assign confidence. Suggest the cheapest test to reduce uncertainty.

CTO

Derive a TechPlan from the PRD/Design/Research. Choose the simplest, secure architecture. Create tasks, call out risks, and branch naming. Hold a brief trade-offs discussion when needed.

Engineer (ENG)

Implement tasks on the feature branch. Keep diffs small. Link commits to tasks. If deviation >20% or security impact → trigger Change Review.

QA

Run tests, write QAReport. If failing, file defects with steps to reproduce and logs. Recommend proceed/block.

10) Metrics & Telemetry (tie to business value)

Lead metric (per item): time-to-task, error rate, adoption.

Process: cycle time, loops to green, retries used.

Quality: escaped defects, a11y violations, security findings.

Cost: model tokens, CI minutes per run.

11) Security & Compliance Basics

Never commit secrets.

Use branch protection; require statuses.

Minimal scopes for PAT.

Add SAST/secret scanning jobs (future phase).

Track model prompts containing sensitive info (mask/redact).

12) State, Resume, & Webhooks

Orchestrator persists per-step state, logs, and artifacts.

Resume continues from last successful step deterministically.

Webhooks (push/PR) refresh artifacts, recompute statuses, and upsert PR summary comment.

Note on persona collaboration (Phase 12):

The orchestrator now maintains a minimal internal `shared_memory` object passed across personas during graph execution and persisted per step. Early personas (Product, Design, Research) record short, deterministic notes that later personas can read. This shared memory is restored on resume to keep execution deterministic and ensure continuity without external calls.

13) Testing the Process (Automation Hooks)

Unit: contract validators for PRD/Design/Research/Plan/QAReport.

Integration: DoR → PR open → statuses → approval → merge (live marker).

Graph: happy path, backtrack, resume, retry-exhaust.

Webhook sim: dry-run path validates comment upsert & status recompute.

Scripts (already in repo):

scripts/test_local.sh – safe local suite (+ webhook sim).

scripts/test_live.sh – live GitHub loop (requires PAT).

14) Naming & Conventions

Branch: feature/<roadmap_item_id>-<slug>

PR summary: marker-based upsert (one canonical comment).

ADR path: docs/adr/ADR-<run>-<slug>.md

15) Roadmap (Next)

Persist graph state (DB), resume endpoint, retries/backoff.

Temporal workflows for durability and observability.

Multi-persona debate w/ “argue-then-decide” scaffolding + cost routing.

Founder cockpit UI (timeline, statuses, approvals, graph state).

15.1) Founder Cockpit UI (Phase 16)

- Operators can open `http://localhost:8000/ui` to access a minimal UI.
- Per‑run page at `/ui/run/<run_id>` surfaces:
  - Run status and created_at (from `/runs/{run_id}`)
  - PR statuses and merge readiness (from `/integrations/github/pr/{run_id}/statuses`)
  - Timeline/history (from `/runs/{run_id}/graph/history`)
  - Metrics (from `/runs/{run_id}/metrics`)
  - Approve and Merge controls (call existing endpoints)
- Gating: when `GITHUB_WRITE_ENABLED=0`, Approve/Merge are disabled and a dry‑run banner is shown.
- No external CDNs; inline CSS/JS only; deterministic and testable.

Vector KB + doc ingestion.

Note on KB file ingestion (Phase 13):

The orchestrator supports local, deterministic file ingestion for citations. Use `POST /kb/ingest-file` with `content_type` of `markdown`, `pdf`, or `text`. Markdown is normalized to text (code fences dropped), PDFs are parsed via local `pypdf`, and content is chunked and embedded using the same deterministic local embedding used elsewhere. No network calls are made during ingestion or search.

16) Scheduler Interactions (Phase 28)

- Purpose: Scale many runs deterministically with fairness and quotas, offline only.
- Controls (env defaults; can be overridden via policy PATCH during a process):
  - `SCHED_ENABLED=1`
  - `SCHED_CONCURRENCY=2` (global max active)
  - `SCHED_TENANT_MAX_ACTIVE=1` (per‑tenant active cap)
  - `SCHED_QUEUE_MAX=100` (backpressure limit)
- API:
  - `POST /scheduler/enqueue {run_id, priority?}` — idempotent add. 400 when capacity exceeded.
  - `GET /scheduler/queue` — deterministic snapshot and sorted list (priority desc; then enqueued_at asc; then run_id asc).
  - `POST /scheduler/step` — leases next eligible run respecting concurrency and quotas; synchronously runs it; returns snapshot and `leased` id.
  - `GET /scheduler/policy` / `PATCH /scheduler/policy` — read/update policy for the process.
  - `GET /scheduler/stats` — counters: `leases`, `skipped_due_to_quota`, `completed`.
- Cockpit: `/ui/scheduler` shows queue, policy, stats, and a Step button. DOM is stable (no timestamps), lists sorted.
- Autonomy: L0/L1 both respect scheduler policies; at L0, enqueue only; at L1, step can be automated by a human operator invoking the Step action.