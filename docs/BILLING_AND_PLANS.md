AI‑CSuite Billing & Plans (Phase 44)

- Plans: community, hosted, enterprise
- Meters per tenant and month (period YYYY-MM): tokens, runs, preview_minutes, storage_mb, api_calls
- Quotas (deterministic):
  - community: tokens 100k, runs 10, preview_minutes 60, storage_mb 128, api_calls 1k
  - hosted: tokens 500k, runs 100, preview_minutes 600, storage_mb 1024, api_calls 10k
  - enterprise: tokens 1M, runs 1000, preview_minutes 6000, storage_mb 10240, api_calls 100k
- Enforcement: community blocks on overages; hosted queues; enterprise never blocks
- Mock invoice generator: deterministic unit prices by plan; returns amount_cents and line items

API
- GET /billing/usage?tenant_id=...&period=YYYY-MM
- POST /billing/plan/set { tenant_id, plan }
- POST /billing/invoice/mock { tenant_id, period? }

Headers
- X-Role: viewer|editor|admin; RBAC gates read/write scopes

# Billing & Plans

Plans:
- Community (self-host): no SLA, limited adapters
- SaaS Starter: usage caps, preview envs, email adapter
- SaaS Pro: advanced adapters, experiments/bandits, SSO
- Enterprise: VPC, custom adapters, RBAC, audit export

Meters: tokens_in/out, runs, preview-deploy minutes, storage, API calls.
Enforcement: soft warn at 80%, block/queue at 100% with override.
