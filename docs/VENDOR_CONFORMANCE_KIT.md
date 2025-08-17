## Vendor Conformance Kit

This kit validates adapter behavior for the Provider Abstraction Layer (PAL). It is deterministic and offline to run in CI and local.

### Scope

Capabilities covered in Phase 31–33:

- AdsProvider (`create_campaign`, `report`, `pause`)
- LifecycleProvider (`send`, `schedule`)
- ExperimentsProvider (stub: `set_flag`, `get_flag`, `ramp`)
- CDPProvider (`upsert_profile`, `ingest_event`, `sync_audience`, `get_profile`)
- VectorStore (`index`, `search`, `swap`)
- LLMGateway (`models`, `route`)

### Pass Criteria

For each adapter under test:

- Idempotent operations must not produce duplicate side-effects.
- Error taxonomy respected: transient → `RetryableError`, permanent → `NonRetryableError`.
- Retry safety: operations are safe under up to 3 attempts.
- Time‑bounded execution under local constraints (no external network in tests).

### How to Run

Use the orchestrator API to execute the suite:

```
POST /providers/conformance/run
Body: {"capabilities": ["ads","lifecycle",...], "adapters": ["mock_ads", ...]}
```

Response includes a summary and per‑adapter report with metrics and error list. The caller may persist JSON reports to `provider_conformance_reports` if desired. All JSON must be stable‑ordered and newline‑terminated when written to disk.

### Fixtures

Deterministic payloads are used to ensure stable outputs:

- Ads: plan `{budget_cents: 1000, geo: "US"}`
- Lifecycle: message `{to: "user@example.com", body: "hi"}`
- CDP: profile `{user_id: "u1", traits: {tier: "gold"}}`
- VectorStore: doc `{id: "d1", text: "hello world"}`
- LLM: policy file with equal weights (example provided)

### Reporting

Each report includes:

- capability, adapter
- pass (boolean)
- metrics: latency_ms, attempts
- errors: []

Reports are returned by the API and may be saved to disk. Ensure deterministic ordering and trailing newline.

### Scaffold Flow

- Endpoint: `POST /self/providers/scaffold`
- Inputs: `capability`, `vendor`, `config`
- Outputs:
  - Adapter module path and unit test path
  - Conformance report written to `apps/orchestrator/orchestrator/reports/conformance/<capability>-<vendor>.json`
  - Optional activation in `providers/providers.yaml` (idempotent)

# Vendor Conformance Kit

Run `make conformance` (or `scripts/providers_conformance.sh`) to validate adapters.

## Required Fixtures
- Ads: campaign plan (budget caps), report time window, pause/resume
- Lifecycle: valid/invalid messages, suppression/consent cases
- Experiments: AB + bandit with seeded RNG, deterministic outcome
- CDP: event batch with merges, profile upsert conflicts
- VectorStore: small corpus, swap scenarios

## Pass Criteria
- No duplicate side effects on retry
- Deterministic outputs with seeded RNG
- Timeouts surfaced as Retryable errors
- Diff report under 1% skew for shadow read
