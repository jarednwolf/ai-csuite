# PATCH_POLICY
_Last updated: 2025-08-17_

Defines risk tiers, directory allow/deny rules, auto‑merge criteria, and rollback rules for self‑work.

## Risk Tiers

- **LOW:** Docs, tests, mock adapters, formatting, comments, type hints.
- **MEDIUM:** API routers, non‑critical services, provider adapters (non‑interface), cockpit data endpoints.
- **HIGH:** Provider **interfaces**, orchestration graph, security/guardrails, workflows, policies.
- **CRITICAL:** DB schema, migrations, secrets, auth/SSO, deployment/IaC.

## Directory Allow/Deny (examples)

- **LOW allow:** `docs/**`, `*.md`, `apps/orchestrator/tests/**`, `apps/orchestrator/orchestrator/providers/adapters/mock_*.py`
- **MEDIUM allow:** `apps/orchestrator/orchestrator/api/**`, `apps/orchestrator/orchestrator/providers/adapters/*.py` (non‑mock), `blueprints/**`, `apps/cockpit/**`
- **HIGH restrict:** `apps/orchestrator/orchestrator/providers/interfaces.py`, `apps/orchestrator/orchestrator/ai_graph/**`, `apps/orchestrator/orchestrator/security/**`, `.github/workflows/**`, `policy/**`, `compliance/**`, `apps/orchestrator/orchestrator/safety/**`, `apps/orchestrator/orchestrator/evals/**`
- **CRITICAL deny (self‑merge prohibited):** `db/schema.sql`, `migrations/**`, `iac/**`, `deployments/**`, secrets or CI credentials

_See `docs/CHANGE_RISK_MATRIX.json` for authoritative mapping._

## Required Gates by Risk Tier

| Tier | Statuses | Other requirements |
|---|---|---|
| LOW | `ai-csuite/self-docs` or `ai-csuite/self-lowrisk`, tests=green | Preview smoke if runtime touched |
| MEDIUM | Core statuses + `ai-csuite/self-review`, preview smoke | Evals baseline unchanged; policy check |
| HIGH | All above + Founder approval (L0), canary if runtime behavior | ADR required; rollback plan attached |
| CRITICAL | Not allowed by self‑work; human‑owned change only | Two‑person rule; maintenance window |

## Auto‑Merge Criteria

- Allowed only for **LOW** risk and **explicitly marked** mechanical changes.
- Tests + policy + preview smoke **must** be green.
- No change to exported symbols or public interfaces.
- Deterministic diffs (no timestamped content).

## Rollback Rules

- Auto‑rollback if any of: eval score < threshold, SLO breach (latency p95 ↑ > 30% from baseline), anomalous cost (run‑cost ↑ > 50%), or safety violation.
- Record ADR for incident; generate postmortem; ingest into KB.
- Rollback path: revert commit → open fix PR via incident playbook.
