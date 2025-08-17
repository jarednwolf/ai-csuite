from __future__ import annotations

import uuid
from typing import Any, Mapping, Sequence

from ..interfaces import LifecycleProvider


class Adapter(LifecycleProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_lifecycle"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def send(self, message: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"id": str(uuid.uuid4()), "ok": True, "echo": dict(message)}

    def schedule(self, batch: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"scheduled": len(list(batch)), "policy": dict(policy)}


