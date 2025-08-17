import os, httpx, json

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post_ok(path, payload=None):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60) if payload is not None else httpx.post(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _try_post(path, payload=None):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60) if payload is not None else httpx.post(f"{BASE}{path}", timeout=60)
    try:
        r.raise_for_status()
        return (True, r.json())
    except Exception:
        try:
            return (False, r.json())
        except Exception:
            return (False, {"error": r.text})


def test_self_feature_canary_rollout_and_rollback(tmp_path):
    # Ensure providers config
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)

    # Register feature (flag default false)
    key = "self.demo_feature"
    reg = _post_ok("/self/feature/register", {"feature_key": key, "title": "Demo", "description": "Demo self feature", "seed": 42})
    assert reg["status"] == "planned"
    assert reg["feature_key"] == key

    # Canary 5% with safe params → expect ramp ok
    canary1 = _post_ok("/self/feature/canary", {
        "feature_key": key,
        "stage": 5,
        "seed": 42,
        "eval_threshold": 0.5,  # permissive for green path
        "safety_text": "This is fine.",
        "latency_base_ms": 100,
        "latency_current_ms": 110,
        "latency_p95_delta_max_ms": 25
    })
    assert canary1["requested_stage"] == 5
    assert canary1["applied_stage"] in {0, 5}  # may be 5 when green
    assert canary1["anomalies"]["eval_below_threshold"] is False
    assert canary1["anomalies"]["safety_blocked"] is False
    assert canary1["anomalies"]["latency_regression"] is False

    # Canary 50% with forced eval/safety/latency anomalies → expect rollback to previous stage
    bad = _post_ok("/self/feature/canary", {
        "feature_key": key,
        "stage": 50,
        "seed": 42,
        "eval_threshold": 0.99,  # force fail against synthetic evals
        "safety_text": "this contains banned term",  # see blocked_terms.json fallback
        "latency_base_ms": 100,
        "latency_current_ms": 200,
        "latency_p95_delta_max_ms": 25
    })
    assert bad["requested_stage"] == 50
    assert bad["rolled_back"] is True
    assert bad["applied_stage"] in {0, 5, 25}
    assert any(bad["anomalies"].values())

    # Artifact
    with open("apps/orchestrator/orchestrator/self/canary_report.json", "r", encoding="utf-8") as f:
        rep = json.load(f)
    assert rep.get("feature_key") == key


