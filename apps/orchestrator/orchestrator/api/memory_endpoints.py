from __future__ import annotations

import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..providers.registry import registry
from ..models import VectorStoreIndex
from ..security import apply_redaction


router = APIRouter()


class IndexDoc(BaseModel):
    id: str
    text: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IndexBody(BaseModel):
    docs: List[IndexDoc]
    redact_mode: str = Field(default="strict")


class SearchResult(BaseModel):
    id: str
    text: str
    source: Optional[str] = None
    chunk: Optional[int] = None


@router.post("/memory/index")
def memory_index(body: IndexBody, db: Session = Depends(get_db)):
    # Enforce memory policy: redact + provenance + dedupe via adapters
    vs = registry().get("vectorstore")
    redacted_docs = []
    for d in body.docs:
        txt = apply_redaction(d.text, mode=body.redact_mode)
        redacted_docs.append({"id": d.id, "text": txt, "source": d.source or d.id, "metadata": d.metadata or {}})
    res = vs.index(redacted_docs)
    row = VectorStoreIndex(id=str(uuid.uuid4()), adapter=str(getattr(vs, "_name", "vectorstore")), index_name=str(res.get("index", "default")), stats={"count": int(res.get("count", 0))})
    db.add(row)
    db.commit()
    return {"indexed": int(res.get("count", 0)), "adapter": row.adapter}


@router.get("/memory/search", response_model=List[SearchResult])
def memory_search(q: str, k: int = 5):
    vs = registry().get("vectorstore")
    hits = vs.search(q, k)
    out: List[SearchResult] = []
    for h in hits:
        out.append(SearchResult(id=str(h.get("id")), text=str(h.get("text")), source=h.get("source"), chunk=h.get("chunk")))
    return out


class SwapBody(BaseModel):
    adapter: str


@router.post("/memory/swap")
def memory_swap(body: SwapBody):
    reg = registry()
    # Swap capability 'vectorstore' adapter to requested mock variant
    if body.adapter not in {"mock_vectorstore", "mock_vectorstore_a", "mock_vectorstore_b"}:
        raise HTTPException(400, "unsupported adapter")
    reg.set_override("vectorstore", body.adapter)
    vs = reg.get("vectorstore")
    res = vs.swap("active")
    return {"status": "ok", "active_adapter": body.adapter, "store": res}



