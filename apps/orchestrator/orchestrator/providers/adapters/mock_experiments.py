from __future__ import annotations

from typing import Any, Mapping, Dict

from ..interfaces import ExperimentsProvider


_FLAGS: Dict[str, Any] = {}
_RAMPS: Dict[str, int] = {}


class Adapter(ExperimentsProvider):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_experiments"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def set_flag(self, key: str, value: Any) -> None:
        _FLAGS[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        return _FLAGS.get(key, default)

    def ramp(self, key: str, stage: int) -> Mapping[str, Any]:
        _RAMPS[key] = int(stage)
        return {"key": key, "stage": int(stage)}


