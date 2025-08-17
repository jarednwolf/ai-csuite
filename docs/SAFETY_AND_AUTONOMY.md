Safety & Autonomy Controls (Phase 42)

Creative Safety

- Blocklists at `apps/orchestrator/orchestrator/safety/policies/blocked_terms.json`.
- Deterministic pre-checks for creative payloads via `POST /safety/moderate {text, channel?, allowlist?}`.
- Returns `{status: allowed|blocked, blocked_terms:[], redacted_text}`; blocks on hits. Records `safety_audits` rows (append-only; redacted).
- A toy classifier is provided in `safety/classifiers/mock_classifier.py` for future extension.

Autonomy Policy

- API: `POST /autonomy/level/set {channel, campaign_id?, level(manual|limited|full)}`. Appends to `autonomy_settings` table. Deterministic; no network.

Spend Controls

- API: `POST /budget/cap/set {channel, campaign_id?, cap_cents}` appends a `budget_caps` row. Combine with anomaly detectors to pause/alert.

Operational Notes

- All logs and stored payloads are redacted (Phase 23). No PII/PHI; no secrets.
- Offline-only behavior for CI. Deterministic outputs and ordering.


