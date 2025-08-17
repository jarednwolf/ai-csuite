from __future__ import annotations

import json, os
from typing import Any, Mapping, Sequence, List, Dict

from ..interfaces import LLMGateway


class Adapter(LLMGateway):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_llm_gateway"
        self._policy_path = (config or {}).get("policy_path")
        self._models = [
            {"id": "mock/small", "cost": 1, "latency": 10, "quality": 0.8, "safety": 0.99},
            {"id": "mock/medium", "cost": 2, "latency": 15, "quality": 0.9, "safety": 0.98},
            {"id": "mock/large", "cost": 4, "latency": 30, "quality": 0.95, "safety": 0.98},
        ]

    def _load_policy(self) -> Mapping[str, Any]:
        path = self._policy_path or "models/policy.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"weights": {"cost": 0.25, "latency": 0.25, "quality": 0.25, "safety": 0.25}, "constraints": {}}

    def models(self) -> Sequence[Mapping[str, Any]]:
        return list(self._models)

    def route(self, prompt: str, tags: Sequence[str]) -> Mapping[str, Any]:
        pol = self._load_policy()
        weights = pol.get("weights", {})
        # Deterministic utility: higher quality/safety better; lower cost/latency better
        def score(m: Mapping[str, Any]) -> float:
            return (
                -weights.get("cost", 0) * float(m.get("cost", 0))
                -weights.get("latency", 0) * float(m.get("latency", 0))
                +weights.get("quality", 0) * float(m.get("quality", 0))
                +weights.get("safety", 0) * float(m.get("safety", 0))
            )
        ranked = sorted(self._models, key=lambda m: (-score(m), str(m.get("id"))))
        chosen = ranked[0] if ranked else {"id": "mock/small"}
        rationale = [
            f"weights={weights}",
            f"chosen={chosen.get('id')}",
        ]
        return {"chosen_model": chosen.get("id"), "policy": pol, "explanations": rationale}


