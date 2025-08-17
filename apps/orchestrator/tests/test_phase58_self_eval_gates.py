import os, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(path, payload=None):
    return httpx.post(f"{BASE}{path}", json=payload, timeout=60)


def test_self_eval_gate_pass_and_fail(tmp_path):
    # Passing case (permissive threshold)
    r_ok = _post("/self/eval/gate", {"threshold": 0.5, "run_id": "self:gate:ok"})
    assert r_ok.status_code == 200, r_ok.text
    data_ok = r_ok.json()
    assert data_ok["status"] == "pass"
    assert data_ok["threshold"] == 0.5

    # Failing case (aggressive threshold beyond max achievable)
    r_bad = _post("/self/eval/gate", {"threshold": 1.01, "run_id": "self:gate:bad"})
    assert r_bad.status_code in {400, 422}
    try:
        j = r_bad.json()
        # Either returned as JSON error detail or body
        if isinstance(j, dict) and j.get("detail"):
            det = j["detail"]
            assert det.get("status") == "fail"
        else:
            assert j.get("status") == "fail"
    except Exception:
        # If not json parsable, treat as a failure
        assert False, r_bad.text


