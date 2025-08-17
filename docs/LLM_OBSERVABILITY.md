LLM Observability & Evals (Phases 24, 40)

Overview

- Deterministic, offline eval harness (Phase 24) runs golden suites in `eval/golden/` and writes `eval/report.json` and `eval/history.json`.
- Phase 40 adds an `LLMObservabilityProvider` abstraction with a mock adapter to capture trace identifiers associated with runs and eval executions, and exposes API endpoints to trigger evals and fetch the latest report.

Provider

- Protocol: `LLMObservabilityProvider` with `trace_start`, `trace_stop`, `log_eval`.
- Adapter: `apps/orchestrator/orchestrator/providers/adapters/mock_llm_observability.py` (deterministic; no network).
- Persistence: `llm_traces` table stores `{id, run_id, trace_id, meta, created_at}`; append-only.

API

- `POST /evals/run` — executes the eval harness in-process; optional `run_id`, `bundle_id`, `threshold` override. Persists an `eval_reports` row and an `llm_traces` row.
- `GET /evals/report` — returns the latest eval report JSON. Deterministic structure: `{suites:[...], summary:{score, passed, failed}}`.

Policy Gate

- Use `scripts/eval_check.sh` to enforce thresholds during CI; non-zero exit on regressions. This can be integrated into merge gating by including eval summary into your policy facts if desired.

Notes

- No external network calls. All artifacts are sorted and newline-terminated where persisted.
- Redaction and audit policies from Phase 23 still apply to any logged details.


