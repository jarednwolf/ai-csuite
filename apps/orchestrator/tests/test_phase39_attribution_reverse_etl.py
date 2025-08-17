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


def test_attribution_and_reverse_etl():
    rep = _post("/attribution/report/run", {"from_date": "2024-01-01", "to_date": "2024-01-31"})
    assert rep["report"]["model"] == "last_touch_utm"

    winners = rep["report"]["winners"]
    members = [{"campaign": w["campaign"], "channel": w["channel"]} for w in winners]
    sync = _post("/audiences/sync", {"name": "winners", "members": members})
    assert sync["status"] == "completed"

    st = _get(f"/audiences/status/{sync['job_id']}")
    assert st["status"] == "completed"


