import os
import httpx

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


def test_shadow_dual_write_and_ramp():
    _ensure_configs()
    # Start shadow: candidate noop_ads (intentionally worse)
    start = _post("/providers/shadow/start", {"capability": "ads", "candidate": "noop_ads", "duration_sec": 30})
    assert start.get("shadow_id")

    # Issue a dual-write compare via conformance runner path
    # The adapter registry doesn't expose compare directly; we trigger an ads op via conformance logic
    res = _post("/providers/conformance/run", {"capabilities": ["ads"]})
    assert res["summary"]["total"] == 1
    # Now ramp through stages and promote to 100
    for stage in (5, 25, 50, 100):
        out = _post(f"/providers/ramp/{stage}", {"capability": "ads", "candidate": "noop_ads"})
        assert out["stage"] == stage

    # After 100, the candidate becomes active; reload confirms by listing providers
    items = _get("/providers")
    caps = {i["capability"]: i for i in items}
    assert caps["ads"]["adapter"] == "noop_ads"


