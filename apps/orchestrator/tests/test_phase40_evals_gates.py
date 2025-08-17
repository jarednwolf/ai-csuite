import os, httpx, json, pathlib, sys

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post_ok(path, payload=None):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60) if payload is not None else httpx.post(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _get_ok(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_evals_run_and_report_gate(tmp_path):
    # Ensure harness runs and report endpoint returns deterministic shape
    res = _post_ok("/evals/run", {"bundle_id": "default", "threshold": 0.5})
    assert res["status"] == "ok"
    rep = _get_ok("/evals/report")
    assert isinstance(rep, dict)
    assert "suites" in rep and "summary" in rep
    assert isinstance(rep["suites"], list)
    assert isinstance(rep["summary"].get("score", 0.0), float)


