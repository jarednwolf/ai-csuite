import os, json
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


def _ensure_policy(weights):
    os.environ["MODELS_POLICY_PATH"] = "models/policy.json"
    os.makedirs("models", exist_ok=True)
    with open("models/policy.json", "w", encoding="utf-8") as f:
        f.write(json.dumps({"weights": weights, "constraints": {}}, sort_keys=True))
        f.write("\n")


def test_llm_policy_routing_deterministic():
    # Ensure providers mapping exists for gateway
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)

    # Equal weights → prefer highest quality + safety, balanced by cost/latency
    _ensure_policy({"cost": 0.25, "latency": 0.25, "quality": 0.25, "safety": 0.25})
    res1 = _post("/llm/route/test", {"input": "hello", "tags": ["test"]})
    assert "chosen_model" in res1
    first_choice = res1["chosen_model"]

    # Bias strongly to cost → prefer smallest
    _ensure_policy({"cost": 1.0, "latency": 0.0, "quality": 0.0, "safety": 0.0})
    res2 = _post("/llm/route/test", {"input": "hello", "tags": ["test"]})
    assert res2["chosen_model"].endswith("small")

    # Update via API with validation
    upd = _post("/llm/policy/update", {"weights": {"cost": 0.0, "latency": 0.0, "quality": 1.0, "safety": 0.0}})
    assert upd["ok"]
    res3 = _post("/llm/route/test", {"input": "hello", "tags": []})
    assert res3["chosen_model"].endswith("large") or res3["chosen_model"].endswith("medium")


