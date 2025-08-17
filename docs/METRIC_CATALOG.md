# Metric Catalog
Metric Catalog (Phase 36)

AI‑CSuite defines tool‑agnostic KPI semantics via a catalog.

- Catalog file: `apps/orchestrator/orchestrator/metrics/metric_catalog.json`
- KPIs: activation, retention_7d, cac, ltv, roas

Endpoints

- GET `/metrics/catalog` → returns the catalog.
- POST `/bi/insights/run` → writes an `InsightReport.json` row in `bi_insights` and returns insights.
- POST `/bi/suggestions/file` → writes `RoadmapSuggestions.json` row and returns a summary.

Design notes

- No external analytics calls; NLQ pass‑through is mocked.
- Outputs are deterministic and sorted where applicable.
Define canonical KPIs to avoid drift across tools.

- Activation: users completing {X} in 7 days
- Retention_7d: pct active D7 over D0 cohort
- CAC: paid_spend / new_customers
- LTV_180: discounted gross profit over 180 days
- ROAS: revenue / ad_spend

Store SQL/snippets + dims + freshness SLO; BI agent reads this.
