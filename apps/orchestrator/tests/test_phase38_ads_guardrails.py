import os, json, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    return r


def _get(p):
    r = httpx.get(f"{BASE}{p}", timeout=30)
    r.raise_for_status()
    return r.json()


def test_ads_budget_guardrails_and_report():
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    src = "apps/orchestrator/orchestrator/config/providers.example.yaml"
    os.makedirs("providers", exist_ok=True)
    with open(src, "r", encoding="utf-8") as f:
        s = f.read()
    with open("providers/providers.yaml", "w", encoding="utf-8") as f:
        f.write(s)

    # Missing budget
    r = _post("/ads/campaigns", {"plan": {"kind": "pmax"}})
    assert r.status_code == 400

    # Valid create
    r2 = _post("/ads/campaigns", {"plan": {"kind": "pmax", "budget_cents": 1000, "spent_cents": 0}})
    r2.raise_for_status()
    cid = r2.json()["id"]
    assert cid

    # Report
    rep = _get(f"/ads/{cid}/report")
    assert rep["campaign_id"] == cid and rep["spend_cents"] >= 0

    # Pause
    p = _post(f"/ads/{cid}/pause", {})
    p.raise_for_status()
    assert p.json()["status"] == "paused"


