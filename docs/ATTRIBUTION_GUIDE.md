Attribution v0 & Reverse‑ETL (Phase 39)

Model

- Deterministic last‑touch UTM with basic sanity checks.
- Output schema: `apps/orchestrator/orchestrator/artifacts/schemas/AttributionReport.schema.json`.

Endpoints

- POST `/attribution/report/run` → returns report id and artifact.
- POST `/audiences/sync` → creates a mock AudienceSync job and marks it complete (reverse‑ETL loop).
- GET `/audiences/status/{id}` → returns job status.

Future work

- Incrementality lift test harness will expand on the reverse‑ETL loop.
# Attribution Guide

v0: last-touch via UTM; sanity checks (impossible paths, bot filters).
v1 (later): geo/temporal holdouts, incrementality lift tests.

Outputs:
- AttributionReport.json + links to experiment/flag states.
Actions:
- Update audiences via CDPProvider; feed winners back to channels.
