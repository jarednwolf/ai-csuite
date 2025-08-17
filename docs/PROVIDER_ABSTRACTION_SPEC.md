## Provider Abstraction Layer (PAL)

This spec defines strict, swappable capability interfaces for external systems and the runtime selection + safety mechanisms used by the orchestrator.

### Capabilities & Protocols

Interfaces are defined in `apps/orchestrator/orchestrator/providers/interfaces.py` as Python Protocols:

- AdsProvider: `create_campaign`, `report`, `pause`
- LifecycleProvider: `send`, `schedule`
- ExperimentsProvider: `set_flag`, `get_flag`, `ramp` (stub for Phase 32; full in Phase 35)
- CDPProvider: `upsert_profile`, `ingest_event`, `sync_audience`, `get_profile`
- VectorStore: `index`, `search`, `swap`
- LLMGateway: `models`, `route`
- LLMObservabilityProvider: `trace_start`, `trace_stop`, `log_eval`

Shared error taxonomy:

- `RetryableError`: transient; triggers retry with jittered backoff
- `NonRetryableError`: permanent; fail fast and classify

### Runtime Selection & DI

The orchestrator uses a lightweight provider registry (`providers/registry.py`) to select the adapter per capability at runtime.

- Config path: env `PROVIDERS_CONFIG_PATH` or `providers/providers.yaml`; fallback to example at `apps/orchestrator/orchestrator/config/providers.example.yaml`.
- Example mapping:

```yaml
capabilities:
  ads: mock_ads
  lifecycle: mock_lifecycle
  experiments: mock_experiments
  cdp: mock_cdp
  vectorstore: mock_vectorstore
  llm_gateway: mock_llm_gateway
```

- Hot‑swap: `POST /providers/reload` reloads mapping; overrides can be applied in-process using the registry (`set_override`) and are reflected in `GET /providers`.

### Conformance Kit

Offline, deterministic suite to validate adapters against PAL contracts:

- Idempotency: repeated calls should not cause duplicate side-effects.
- Error taxonomy: transient errors raise `RetryableError`; permanent raise `NonRetryableError`.
- Retries/Backoff: caller applies capped retries (default 3) with jitter; adapters must be side-effect safe.
- Timeouts: operations should complete within bounded time in local tests.
- Metrics hooks: log capability, adapter, latency_ms, attempts, error class.

Run: `POST /providers/conformance/run` with optional filters.

Response shape:

```json
{
  "summary": {"total": 3, "passed": 3, "failed": 0},
  "reports": [
    {"capability": "ads", "adapter": "mock_ads", "pass": true, "metrics": {"latency_ms": 1, "attempts": 1}, "errors": []}
  ]
}
```

Reports are newline‑terminated, stable ordered, and may be persisted by the caller.

### Shadow Mode & Ramp Controller (Phase 32)

The Shadow Manager runs current + candidate adapters in parallel to measure parity and performance before a cutover.

- Start: `POST /providers/shadow/start` with `{capability, candidate, duration_sec}` → `shadow_id`.
- Dual‑write and read‑compare: the orchestrator executes both adapters and records a deterministic diff (`fields_mismatch`).
- Ramp: `POST /providers/ramp/{stage}` with `{capability, candidate}`; stages in `{5,25,50,100}`. At 100, the candidate is promoted to active and the shadow ends.
- Stop: `POST /providers/shadow/stop` to end early.

Kill‑switch and rollback: if SLO/ROAS regress, ramp should be reversed; tests inject mismatches to trigger rollback behavior.

### Auto‑Vendor Swap Pipeline (Phase 61)

- The orchestrator may initiate a vendor swap autonomously within budget and safety caps.
- Helper endpoints (local only) simplify deterministic tests:
  - `POST /providers/shadow/start/simple` → start a shadow for `{capability, candidate}` with safe defaults.
  - `POST /providers/shadow/compare-once` → run one deterministic dual‑write compare and return a mismatch count.
- Decision policy (offline): proceed to ramp only when mismatches==0 and budget caps (Phase 19) are respected.
- Artifact: `self/vendor_shadow_report.json` records the decision and inputs.

### LLM Gateway & Policy Routing (Phase 33)

The orchestrator routes prompts to models using a policy file (`models/policy.json`, env `MODELS_POLICY_PATH`).

Policy example:

```json
{"weights": {"cost": 0.25, "latency": 0.25, "quality": 0.25, "safety": 0.25}, "constraints": {}}
```

Endpoints:

- `POST /llm/route/test` → choose model and return rationale
- `GET /llm/models` → list models
- `POST /llm/policy/update` → validate and write policy (sorted keys, trailing newline)

Adapters:

- `mock_llm_gateway` — deterministic, offline models and scoring
- `litellm_gateway`, `openrouter_gateway` — feature‑flagged; no network in tests

### Telemetry & Logging

All PAL operations must log capability, adapter, latency_ms, attempts, error class, and rationales when routing.

Secrets are never logged; tokens are redacted. All JSON outputs are deterministically ordered and newline‑terminated when persisted.

# Provider Abstraction Layer (PAL) — Capability Contracts

**Purpose:** Make every external tool swappable without changing agent logic.

## Capabilities & Interfaces
- AdsProvider: create_campaign, pause, report
- LifecycleProvider: send, schedule, preview
- ExperimentsProvider: start_ab, start_bandit, assign, report, ramp
- CDPProvider: upsert_profile, ingest_event, sync_audience, get_profile
- VectorStore: index, search, swap
- LLMGateway: route(prompt, tags) → model/result + metrics
- LLMObservabilityProvider: trace_start/stop, log_eval, link(run_id)

## Runtime Selection
- Registry reads `providers/*.yaml` mapping capability → adapter.
- Feature flag `provider.<capability>.candidate` enables shadow mode.

## Conformance
- Golden tests validate: idempotency, retries + backoff, timeout semantics,
  error taxonomy (Retryable/NonRetryable), metrics (latency, error rate),
  and payload shape parity with mocks.

## Shadow & Ramp
- Dual‑write, read‑compare; store diff report per capability.
- Ramp stages: 5/25/50/100% with auto‑rollback on SLO breach.

## Telemetry
- Emit spans: capability, vendor, latency_ms, status, retries.

## Scaffold → Conformance → (optional) Shadow

- Scaffold: Use `POST /self/providers/scaffold` with `{capability, vendor, config}` to generate an adapter skeleton in `apps/orchestrator/orchestrator/providers/adapters/<vendor>.py` and a minimal unit test. The call is idempotent.
- Conformance: The scaffold flow runs a local, deterministic conformance kit and writes a report to `apps/orchestrator/orchestrator/reports/conformance/<capability>-<vendor>.json` (sorted keys, newline-terminated). Summary is also persisted in DB as `provider_conformance_reports`.
- Registration: The vendor is recorded in `providers/providers.yaml` under `adapters:` and, if requested, mapped under `capabilities:` to activate. Activation is optional and safe in CI dry-run.
- Shadow (optional): After a vendor passes, you may start shadow via `POST /providers/shadow/start` and ramp with `POST /providers/ramp/{stage}`. In CI, shadow start is disabled; only dry-run metadata is produced.
