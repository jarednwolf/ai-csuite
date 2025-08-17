# Marketing & BI Artifact Contracts (Tool‑agnostic)
Marketing & BI Artifact Contracts (Phase 37)

Artifacts

- `MarketingBrief.json` → see schema at `apps/orchestrator/orchestrator/artifacts/schemas/MarketingBrief.schema.json`
- `ChannelPlan.json` → see schema at `apps/orchestrator/orchestrator/artifacts/schemas/ChannelPlan.schema.json`
- `CreativeBatch.json` → see schema at `apps/orchestrator/orchestrator/artifacts/schemas/CreativeBatch.schema.json`

Endpoints

- POST `/lifecycle/send` with consent enforcement and pre‑send compliance checks.
- POST `/lifecycle/sequence` rate‑limits and schedules batch.
- POST `/lifecycle/preview` renders a deterministic preview.

Compliance & Safety

- Consent flags enforced; suppression via blocked terms.
- Rate limits applied per request; no external sends in CI.
## Marketing
- MarketingBrief.json { audience, value_prop, constraints[], brand{tone} }
- ChannelPlan.json { channels[{name,budget{daily},guardrails{max_cpa}}] }
- CreativeBatch.json [{id,type,copy,assets[],notes}]
- ExperimentPlan.json { hypothesis, primary_metric, variants, min_sample, stopping }
- CampaignRun.json { id, plan_ref, changes[], approvals[], timestamps }
- AttributionReport.json { window, model, cpa, roas, notes }
- WeeklyGrowthBrief.md (markdown summary)

## BI
- MetricCatalog.json [ { name, owner, formula/sql, dims, freshness } ]
- InsightReport.json { anomalies[], drivers[], recs[] }
- RoadmapSuggestions.json [{title, impact, effort, confidence, links[]}]
- CostLedger.json [{run_id, persona, tokens, cost_usd}]
