from __future__ import annotations

from typing import Any, Mapping, Sequence, Dict, List

from ..interfaces import VectorStore


_INDEX: List[Mapping[str, Any]] = []
_TARGET = "vs-a"


class Adapter(VectorStore):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_vectorstore_a"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def index(self, docs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        for d in docs:
            _INDEX.append(dict(d))
        # quick dedupe by id
        seen = set()
        deduped: List[Mapping[str, Any]] = []
        for d in _INDEX:
            did = str(d.get("id"))
            if did in seen:
                continue
            seen.add(did)
            deduped.append(d)
        _INDEX[:] = deduped
        return {"count": len(list(docs)), "index": _TARGET}

    def search(self, query: str, k: int = 5) -> Sequence[Mapping[str, Any]]:
        hits = [d for d in _INDEX if query.lower() in str(d.get("text", "")).lower()]
        # deterministic rank by length then id
        hits.sort(key=lambda d: (len(str(d.get("text",""))), str(d.get("id"))))
        return hits[:k]

    def swap(self, target: str) -> Mapping[str, Any]:
        global _TARGET
        _TARGET = str(target)
        return {"active": _TARGET}



