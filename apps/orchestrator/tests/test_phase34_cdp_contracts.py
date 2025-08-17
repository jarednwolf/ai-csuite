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


def test_cdp_event_contracts_and_profile():
    # Ensure providers mapping exists
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)

    # Ingest identify + track
    body = {
        "events": [
            {"type": "identify", "user_id": "u1", "traits": {"tier": "gold"}, "consent": {"email_opt_in": True}},
            {"type": "track", "user_id": "u1", "event": "signup", "properties": {"plan": "pro"}},
        ]
    }
    res = _post("/cdp/events/ingest", body)
    assert res["ok"] and res["ingested"] == 2

    # Sync a small audience
    res2 = _post("/cdp/audiences/sync", {"name": "vip", "members": [{"user_id": "u1"}]})
    assert res2["status"] == "completed"

    # Profile fetch
    prof = _get("/cdp/profile/u1")
    assert prof["user_id"] == "u1"
    assert prof["traits"]["tier"] == "gold"


