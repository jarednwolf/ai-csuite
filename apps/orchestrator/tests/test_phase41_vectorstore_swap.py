import os, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post_ok(path, payload=None):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60) if payload is not None else httpx.post(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _get_ok(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_vectorstore_swap_and_search_parity(tmp_path):
    # Index a small corpus
    docs = [
        {"id": "d1", "text": "Hello World", "source": "s1"},
        {"id": "d2", "text": "World of Vector Stores", "source": "s2"},
    ]
    idx = _post_ok("/memory/index", {"docs": docs})
    assert idx["indexed"] >= 2
    # Baseline search
    hits1 = _get_ok("/memory/search?q=world&k=5")
    assert isinstance(hits1, list) and len(hits1) >= 1
    # Swap adapter
    swap = _post_ok("/memory/swap", {"adapter": "mock_vectorstore_b"})
    assert swap["active_adapter"] == "mock_vectorstore_b"
    # Re-index and ensure search still returns relevant results
    _post_ok("/memory/index", {"docs": docs})
    hits2 = _get_ok("/memory/search?q=world&k=5")
    assert isinstance(hits2, list) and len(hits2) >= 1
    # Deterministic fields present
    for h in hits2:
        assert "id" in h and "text" in h


