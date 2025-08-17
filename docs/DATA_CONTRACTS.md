AI‑CSuite Data Contracts (Phase 34)

This document defines canonical contracts for the CDP event pipeline.

- Event schema file: `apps/orchestrator/orchestrator/artifacts/schemas/events.schema.json`
- Supported types: `track`, `identify`, `alias`, `group`
- Minimal validation is enforced server‑side; fields are normalized to snake_case on ingest.

Endpoints

- POST `/cdp/events/ingest`: body `{ events: [...] }` where each event matches the schema. Append‑only persisted in `cdp_events`.
- POST `/cdp/audiences/sync`: upserts an audience with member list; returns a deterministic job id and latency.
- GET `/cdp/profile/{id}`: returns a normalized profile view from the configured `CDPProvider`.

Provider Responsibilities

- `upsert_profile(profile)`: handles identity reconciliation, traits, and consent flags.
- `ingest_event(event)`: processes event stream for downstream modeling/predictions.
- `sync_audience(audience)`: pushes audience to destinations (mocked offline).
- `get_profile(user_id)`: returns traits and optional predictions.

Security & Observability

- No PII is logged; payloads are redacted in audit logs.
- Each operation records latency and attempts in the response where relevant.


