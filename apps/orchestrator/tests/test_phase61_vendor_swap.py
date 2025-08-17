import os, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    r.raise_for_status()
    return r.json()


def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=30)
    r.raise_for_status()
    return r.json()


def _ensure_configs():
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)


def test_phase61_vendor_swap_shadow_to_ramp():
    _ensure_configs()
    # Start shadow for ads -> noop_ads (candidate intentionally different)
    start = _post("/providers/shadow/start/simple", {"capability": "ads", "candidate": "noop_ads"})
    assert start.get("shadow_id")

    # Compare once
    cmp_res = _post("/providers/shadow/compare-once", {"capability": "ads"})
    # Build a report based on mismatches and ensure policy reaction
    mism = int(cmp_res.get("mismatches", 0)) if isinstance(cmp_res, dict) else 0
    # If mismatches==0 we can ramp; else hold (deterministic candidate here has mismatches > 0)
    if mism == 0:
        for stage in (5, 25, 50, 100):
            out = _post(f"/providers/ramp/{stage}", {"capability": "ads", "candidate": "noop_ads"})
            assert out["stage"] == stage
        items = _get("/providers")
        caps = {i["capability"]: i for i in items}
        assert caps["ads"]["adapter"] == "noop_ads"
    else:
        # ensure baseline remains the same (no ramp applied)
        items = _get("/providers")
        caps = {i["capability"]: i for i in items}
        assert caps["ads"]["adapter"] != "noop_ads"


