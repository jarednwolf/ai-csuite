import os, hashlib
import numpy as np
from typing import List

EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))

def embed_text_local(text: str, dim: int = EMBED_DIM) -> List[float]:
    """
    Deterministic 'good-enough' local embedding (no external calls).
    - Seeded by SHA-256 of the text.
    - Combines a random normal vector with a simple byte-histogram signal.
    - Normalized to unit length for cosine similarity via dot product.
    NOT semantic-quality; swap with a real provider later (BYOK).
    """
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(dim,)).astype(np.float32)

    if text:
        hist = np.zeros(dim, dtype=np.float32)
        for b in text.encode("utf-8"):
            hist[b % dim] += 1.0
        v += hist

    norm = float(np.linalg.norm(v) + 1e-8)
    return (v / norm).tolist()

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) + 1e-8) * (np.linalg.norm(b) + 1e-8)
    return float(np.dot(a, b) / denom)


