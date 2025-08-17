import os, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(path, payload=None):
    return httpx.post(f"{BASE}{path}", json=payload, timeout=60)


def _post_ok(path, payload=None):
    r = _post(path, payload)
    r.raise_for_status()
    return r.json()


def test_moderation_blocks_unsafe_creative(tmp_path):
    bad = _post("/safety/moderate", {"text": "This is illegal content"})
    assert bad.status_code == 400
    js = bad.json()
    assert js.get("status") == "blocked" and "illegal" in ",".join(js.get("blocked_terms", []))


def test_autonomy_and_budget_caps_set(tmp_path):
    res1 = _post_ok("/autonomy/level/set", {"channel": "ads", "level": "limited"})
    assert res1["level"] == "limited"
    res2 = _post_ok("/budget/cap/set", {"channel": "ads", "campaign_id": "c1", "cap_cents": 5000})
    assert res2["cap_cents"] == 5000


