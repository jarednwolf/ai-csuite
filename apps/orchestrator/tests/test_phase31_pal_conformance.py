import os
import httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=30)
    r.raise_for_status()
    return r.json()


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    r.raise_for_status()
    return r.json()


def _ensure_configs():
    # Point to example configs deterministically
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    os.environ["MODELS_POLICY_PATH"] = "models/policy.json"
    # Prepare example files for the app to read
    src_prov = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src_prov, "r", encoding="utf-8") as f:
        content = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(content)
    src_pol = "apps/orchestrator/orchestrator/config/models.policy.example.json"
    os.makedirs("models", exist_ok=True)
    with open(src_pol, "r", encoding="utf-8") as f:
        content = f.read()
    with open("models/policy.json", "w", encoding="utf-8") as f:
        f.write(content)


def test_pal_conformance_and_hot_swap():
    _ensure_configs()
    # List providers
    items = _get("/providers")
    assert isinstance(items, list)
    caps = {i["capability"]: i for i in items}
    assert "ads" in caps and caps["ads"]["adapter"] == "mock_ads"
    assert caps["llm_gateway"]["healthy"] is True

    # Run conformance (subset)
    res = _post("/providers/conformance/run", {"capabilities": ["ads", "lifecycle", "llm_gateway"]})
    assert res["summary"]["total"] >= 3
    assert res["summary"]["failed"] == 0

    # Hot reload should keep same mapping when file unchanged
    reloaded = _post("/providers/reload", {})
    assert "active" in reloaded and reloaded["active"]["ads"] == "mock_ads"


