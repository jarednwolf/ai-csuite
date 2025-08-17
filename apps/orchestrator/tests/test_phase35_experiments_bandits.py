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


def test_experiments_bandits_and_flags():
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)

    plan = {"id": "exp1", "variants": {"A": 0.3, "B": 0.7}, "flags": {"feat": True}}
    res = _post("/experiments/start", {"experiment_id": "exp1", "plan": plan, "seed": 42})
    assert res["experiment_id"] == "exp1"
    assert res["arm"] in {"A", "B"}

    rep = _get("/experiments/exp1/report")
    assert rep["id"] == "exp1"
    assert rep["winner"] == res["arm"]

    ramp = _post("/flags/ramp", {"key": "cap.ads", "stage": 25})
    assert ramp["ok"]


