import os
import json
import httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post_ok(path, payload=None):
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=60) if payload is not None else httpx.post(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def test_provider_adapter_scaffold_and_conformance(tmp_path):
    # Ensure providers config path is set and exists
    os.environ["PROVIDERS_CONFIG_PATH"] = "providers/providers.yaml"
    os.makedirs("providers", exist_ok=True)
    if not os.path.exists("providers/providers.yaml"):
        with open("providers/providers.yaml", "w", encoding="utf-8") as f:
            f.write("adapters: {}\ncapabilities: {}\n")

    payload = {
        "capability": "ads",
        "vendor": "acme_ads",
        "config": {"example": True},
        "dry_run": True,
        "activate": False,
        "seed": 42,
    }
    res = _post_ok("/self/providers/scaffold", payload)
    assert res["status"] == "ok"
    assert res["capability"] == "ads"
    assert res["vendor"] == "acme_ads"
    assert res["adapter_path"].endswith("providers/adapters/acme_ads.py")
    assert res["unit_test_path"].endswith("tests/test_adapter_acme_ads.py")
    assert res["conformance_report_path"].endswith("reports/conformance/ads-acme_ads.json")

    # Artifact exists and is deterministic
    with open(res["conformance_report_path"], "r", encoding="utf-8") as f:
        rep = json.load(f)
    assert rep["summary"]["passed"] == 1 and rep["summary"]["failed"] == 0
    assert rep["reports"][0]["capability"] == "ads"
    assert rep["reports"][0]["adapter"] == "acme_ads"

    # Idempotent re-run
    res2 = _post_ok("/self/providers/scaffold", payload)
    assert res2["adapter_path"] == res["adapter_path"]
    assert res2["unit_test_path"] == res["unit_test_path"]
    with open(res2["conformance_report_path"], "r", encoding="utf-8") as f:
        rep2 = json.load(f)
    assert rep2 == rep


