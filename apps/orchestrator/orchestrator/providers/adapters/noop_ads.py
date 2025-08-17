from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..interfaces import AdsProvider, NonRetryableError


class Adapter(AdsProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "noop_ads"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def create_campaign(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        # Intentionally subpar: simulate candidate regression by missing fields
        return {"id": "noop", "status": "active"}

    def report(self, query: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        # Missing spend field to trigger diff
        return [{"date": "2024-01-01", "impressions": 1, "clicks": 0}]

    def pause(self, campaign_id: str) -> None:
        return None


