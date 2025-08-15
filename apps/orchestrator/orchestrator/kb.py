import uuid, math
from typing import List, Dict, Any
from io import BytesIO
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


def ingest_document(db: Session, tenant_id: str, project_id: str, kind: str, ref_id: str, text: str) -> int:
    """
    Deterministic document ingestion helper. Normalizes to chunks, embeds locally,
    and writes rows in a single commit. Mirrors ingest_text to avoid duplication
    in endpoints while keeping a semantic name for file-based ingestion.
    """
    return ingest_text(db, tenant_id=tenant_id, project_id=project_id, kind=kind, ref_id=ref_id, text=text)


def markdown_to_text(text: str) -> str:
    """
    Very small, deterministic markdown → text normalizer:
    - Drop fenced code blocks ```...```
    - Strip inline code backticks
    - Convert [label](url) → label and ![alt](url) → alt
    - Remove heading markers (#), blockquotes (>), list markers (-, *, +) at line start
    - Remove emphasis markers (*, _, ~) while preserving inner text
    - Collapse excessive blank lines
    """
    import re

    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not s:
        return ""

    # Remove fenced code blocks
    s = re.sub(r"```[\s\S]*?```", "\n", s)

    # Links and images
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)  # images → alt text
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)    # links → label

    # Inline code backticks
    s = s.replace("`", "")

    # Line-based cleanup
    lines = []
    for line in s.split("\n"):
        # Strip common markdown prefixes
        line2 = line.lstrip()
        line2 = re.sub(r"^(#{1,6})\s*", "", line2)  # headings
        line2 = re.sub(r"^>+\s*", "", line2)        # blockquote
        line2 = re.sub(r"^([\-*+])\s+", "", line2) # list markers
        # Emphasis markers (keep inner text)
        line2 = line2.replace("**", "").replace("__", "")
        line2 = line2.replace("*", "").replace("_", "").replace("~", "")
        # Table pipes → spaces
        line2 = line2.replace("|", " ")
        lines.append(line2)

    s = "\n".join(lines)
    # Collapse 3+ newlines to 2, and strip
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def pdf_to_text_bytes(pdf_bytes: bytes) -> str:
    """
    Local-only PDF text extraction using pypdf. Returns empty string on failure.
    Deterministic behavior (no network, no randomness).
    """
    if not pdf_bytes:
        return ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        texts: List[str] = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
                if t:
                    texts.append(t)
            except Exception:
                # Continue extracting other pages deterministically
                continue
        return "\n".join(texts).strip()
    except Exception:
        return ""

