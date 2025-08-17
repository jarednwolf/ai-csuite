from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..interfaces import RetryableError, NonRetryableError


class Adapter:
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config = dict(config or {})
        self._state = {"calls": 0}

    def health(self) -> Mapping[str, Any]:
        return {"ok": True, "calls": int(self._state.get("calls", 0))}

    def create_campaign(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return {"id": "camp_1", "status": "active", "plan": dict(plan or {})}

    def report(self, query: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return [{"campaign_id": str(query.get("campaign_id") or "camp_1"), "spend_cents": 0, "impressions": 0}]

    def pause(self, campaign_id: str) -> None:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return None
