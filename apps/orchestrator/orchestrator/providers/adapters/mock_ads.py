from __future__ import annotations

import time, uuid
from typing import Any, Mapping, Sequence, Dict, List

from ..interfaces import AdsProvider, RetryableError, NonRetryableError


_CAMPAIGNS: Dict[str, Mapping[str, Any]] = {}


class Adapter(AdsProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_ads"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def create_campaign(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        cid = plan.get("id") or str(uuid.uuid4())
        out = {"id": cid, "status": "active", "plan": dict(sorted(plan.items(), key=lambda kv: str(kv[0])))}
        _CAMPAIGNS[cid] = out
        # deterministic small delay for latency metric
        time.sleep(0.001)
        return out

    def report(self, query: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        cid = query.get("campaign_id")
        base = [{"date": "2024-01-01", "impressions": 100, "clicks": 10, "spend_cents": 123},
                {"date": "2024-01-02", "impressions": 110, "clicks": 11, "spend_cents": 145}]
        # stable sort
        base.sort(key=lambda r: r["date"])
        return base

    def pause(self, campaign_id: str) -> None:
        if campaign_id in _CAMPAIGNS:
            _CAMPAIGNS[campaign_id] = dict(_CAMPAIGNS[campaign_id], status="paused")
        return None


