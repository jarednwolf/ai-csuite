from __future__ import annotations

from typing import Any, Mapping, Sequence, Dict, List

from ..interfaces import VectorStore


_INDEX: List[Mapping[str, Any]] = []
_TARGET = "vs-b"


class Adapter(VectorStore):
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._name = "mock_vectorstore_b"

    def health(self) -> Mapping[str, Any]:
        return {"ok": True}

    def index(self, docs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        # chunking simulation: split long docs at 80 chars boundaries with provenance
        count = 0
        for d in docs:
            text = str(d.get("text", ""))
            src = str(d.get("source", d.get("id", "")))
            chunks = [text[i:i+80] for i in range(0, len(text), 80)] or [text]
            for idx, ch in enumerate(chunks):
                _INDEX.append({"id": f"{d.get('id')}-{idx}", "text": ch, "source": src, "chunk": idx})
                count += 1
        return {"count": count, "index": _TARGET}

    def search(self, query: str, k: int = 5) -> Sequence[Mapping[str, Any]]:
        hits = [d for d in _INDEX if query.lower() in str(d.get("text", "")).lower()]
        # deterministic rank by chunk index then id
        hits.sort(key=lambda d: (int(d.get("chunk", 0)), str(d.get("id"))))
        return hits[:k]

    def swap(self, target: str) -> Mapping[str, Any]:
        global _TARGET
        _TARGET = str(target)
        return {"active": _TARGET}



