import uuid, math
from typing import List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
from .models import KbChunk
from .embeddings import embed_text_local, cosine

def _chunk_text(text: str, target_chars: int = 800, overlap: int = 120) -> List[str]:
    """
    Naive chunker by character count with overlap. Works for MVP without tokenizers.
    """
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + target_chars)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def ingest_text(db: Session, tenant_id: str, project_id: str, kind: str, ref_id: str, text: str) -> int:
    chunks = _chunk_text(text)
    count = 0
    for c in chunks:
        emb = embed_text_local(c)
        row = KbChunk(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            kind=kind,
            ref_id=ref_id or "",
            text=c,
            emb=emb,
        )
        db.add(row)
        count += 1
    db.commit()
    return count

def search(db: Session, tenant_id: str, project_id: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Simple in-DB fetch then Python-side cosine ranking (keeps SQLite-compatible tests).
    """
    if not query:
        return []
    q_emb = np.array(embed_text_local(query), dtype=np.float32)
    rows = (
        db.query(KbChunk)
          .filter(KbChunk.tenant_id == tenant_id, KbChunk.project_id == project_id)
          .order_by(KbChunk.created_at.desc())
          .limit(500)
          .all()
    )
    scored = []
    for r in rows:
        v = np.array(r.emb, dtype=np.float32)
        s = cosine(q_emb, v)
        scored.append((s, r))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:max(1, k)]
    return [
        {"id": r.id, "kind": r.kind, "ref_id": r.ref_id, "text": r.text, "score": round(float(s), 4)}
        for s, r in top
    ]


