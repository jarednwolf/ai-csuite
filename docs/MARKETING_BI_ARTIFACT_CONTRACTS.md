# Marketing & BI Artifact Contracts (Tool‑agnostic)

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
