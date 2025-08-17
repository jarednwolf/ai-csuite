from __future__ import annotations

import time
import uuid
from typing import Any, Mapping

from ..interfaces import LLMObservabilityProvider


class Adapter(LLMObservabilityProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_llm_observability"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def trace_start(self, run_id: str, meta: Mapping[str, Any]) -> str:
        # Deterministic-ish, but unique: prefix run id when provided
        base = (run_id or "")[:8]
        return f"tr_{base}_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"

    def trace_stop(self, trace_id: str, meta: Mapping[str, Any]) -> None:
        return None

    def log_eval(self, name: str, score: float, meta: Mapping[str, Any]) -> None:
        # No-op for mock; real impl would forward to tracing backend
        return None



