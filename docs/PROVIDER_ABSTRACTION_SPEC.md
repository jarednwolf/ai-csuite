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
