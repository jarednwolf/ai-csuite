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
