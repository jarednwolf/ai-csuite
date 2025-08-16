# Billing & Plans

Plans:
- Community (self-host): no SLA, limited adapters
- SaaS Starter: usage caps, preview envs, email adapter
- SaaS Pro: advanced adapters, experiments/bandits, SSO
- Enterprise: VPC, custom adapters, RBAC, audit export

Meters: tokens_in/out, runs, preview-deploy minutes, storage, API calls.
Enforcement: soft warn at 80%, block/queue at 100% with override.
