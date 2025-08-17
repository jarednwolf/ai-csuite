from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..interfaces import LLMGateway


class Adapter(LLMGateway):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "litellm_gateway"
        self._enabled = False  # feature-flagged off in tests

    def health(self) -> Mapping[str, Any]:
        return {"ok": self._enabled}

    def models(self) -> Sequence[Mapping[str, Any]]:
        return []

    def route(self, prompt: str, tags: Sequence[str]) -> Mapping[str, Any]:
        # No network calls in tests; return a deterministic fallback
        return {"chosen_model": "litellm/disabled", "policy": {"disabled": True}, "explanations": ["feature-flagged off"]}


