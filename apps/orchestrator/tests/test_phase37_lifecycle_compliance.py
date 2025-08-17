import os, json, httpx

BASE = os.getenv("ORCH_BASE", "http://127.0.0.1:8001")


def _post(p, j):
    r = httpx.post(f"{BASE}{p}", json=j, timeout=30)
    return r


def test_lifecycle_compliance_and_preview():
    # Preview render deterministically
    pr = httpx.post(f"{BASE}/lifecycle/preview", json={"channel": "email", "body": {"headline": "Hello"}}, timeout=30)
    pr.raise_for_status()
    assert pr.json()["render"]["length"] >= 5

    # Blocked term enforcement
    r = _post("/lifecycle/send", {"channel": "email", "to": "u@example.com", "body": {"text": "risk-free"}})
    assert r.status_code == 400

    # Consent enforced
    r2 = _post("/lifecycle/send", {"channel": "email", "to": "u@example.com", "body": {"text": "ok"}, "consent": {"email_opt_in": False}})
    assert r2.status_code == 400

    # Valid send
    r3 = _post("/lifecycle/send", {"channel": "email", "to": "u@example.com", "body": {"text": "hi"}, "consent": {"email_opt_in": True}})
    r3.raise_for_status()
    assert r3.json()["status"] == "sent"


