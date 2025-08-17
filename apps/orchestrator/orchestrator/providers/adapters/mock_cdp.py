from __future__ import annotations

from typing import Any, Mapping, Optional, Dict

from ..interfaces import CDPProvider


_PROFILES: Dict[str, Mapping[str, Any]] = {}


class Adapter(CDPProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_cdp"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def upsert_profile(self, profile: Mapping[str, Any]) -> None:
        uid = str(profile.get("user_id"))
        _PROFILES[uid] = dict(profile)

    def ingest_event(self, event: Mapping[str, Any]) -> None:
        uid = str(event.get("user_id"))
        prof = dict(_PROFILES.get(uid) or {"user_id": uid})
        events = list(prof.get("events", []))
        events.append(dict(event))
        prof["events"] = events
        _PROFILES[uid] = prof

    def sync_audience(self, audience: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"synced": True, "size": len(list(audience.get("members", [])))}

    def get_profile(self, user_id: str) -> Optional[Mapping[str, Any]]:
        return _PROFILES.get(str(user_id))


