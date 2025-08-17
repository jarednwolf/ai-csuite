import os, json, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    r.raise_for_status()
    return r.json()


def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=30)
    r.raise_for_status()
    return r.json()


def test_metric_catalog_and_bi_outputs():
    cat = _get("/metrics/catalog")
    assert "kpis" in cat and "activation" in cat["kpis"]

    ins = _post("/bi/insights/run", {"run_id": None, "query": "weekly"})
    assert ins["insights"]["top_kpis"]

    sug = _post("/bi/suggestions/file", {"run_id": None, "context": {}})
    assert sug["filed"] and sug["count"] >= 1


