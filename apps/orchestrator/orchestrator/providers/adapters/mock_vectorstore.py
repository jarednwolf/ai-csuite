from __future__ import annotations

from typing import Any, Mapping, Sequence, Dict, List

from ..interfaces import VectorStore


_INDEX: List[Mapping[str, Any]] = []
_TARGET = "index-v1"


class Adapter(VectorStore):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_vectorstore"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def index(self, docs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        for d in docs:
            _INDEX.append(dict(d))
        return {"count": len(list(docs))}

    def search(self, query: str, k: int = 5) -> Sequence[Mapping[str, Any]]:
        # Deterministic substring match
        hits = [d for d in _INDEX if query.lower() in str(d.get("text", "")).lower()]
        return hits[:k]

    def swap(self, target: str) -> Mapping[str, Any]:
        global _TARGET
        _TARGET = str(target)
        return {"active": _TARGET}


