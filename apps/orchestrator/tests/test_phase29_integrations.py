import os, httpx

BASE = os.getenv("ORCH_BASE", "http://localhost:8000")


def _get_ok(path):
    r = httpx.get(f"{BASE}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _post_ok(path, payload=None):
    if payload is None:
        r = httpx.post(f"{BASE}{path}", timeout=60)
    else:
        r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _patch_ok(path, payload):
    r = httpx.patch(f"{BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _post_400(path, payload=None):
    if payload is None:
        r = httpx.post(f"{BASE}{path}", timeout=60)
    else:
        r = httpx.post(f"{BASE}{path}", json=payload, timeout=60)
    assert r.status_code == 400
    return r.json()


def test_registry_lists_mock_echo_and_deterministic():
    res = _get_ok("/integrations/partners")
    assert isinstance(res, list) and len(res) >= 1
    ids = [x["partner_id"] for x in res]
    assert ids == sorted(ids)
    assert "mock_echo" in ids


def test_policy_patch_and_get_reflects_updates():
    pol = _get_ok("/integrations/partners/mock_echo/policy")
    # Patch values
    upd = _patch_ok("/integrations/partners/mock_echo/policy", {
        "rate_limit": 2, "retry_max": 4, "backoff_ms": 10, "circuit_threshold": 3, "window_tokens": 1
    })
    assert upd["rate_limit"] == 2 and upd["retry_max"] == 4 and upd["backoff_ms"] == 10 and upd["circuit_threshold"] == 3 and upd["window_tokens"] == 1
    # Get again
    pol2 = _get_ok("/integrations/partners/mock_echo/policy")
    assert pol2 == upd


def test_rate_limit_with_tick_and_counters():
    _patch_ok("/integrations/partners/mock_echo/policy", {"rate_limit": 1, "window_tokens": 1})
    _post_ok("/integrations/partners/mock_echo/reset")
    # First call consumes token and succeeds
    ok1 = _post_ok("/integrations/partners/mock_echo/call", {"op": "echo", "payload": {"payload": "a"}})
    assert ok1["status"] == "ok" and ok1["rate_remaining"] == 0
    # Second call is rate-limited
    err = _post_400("/integrations/partners/mock_echo/call", {"op": "echo", "payload": {"payload": "b"}})
    assert err["status"] == "rate_limited"
    # Tick refills
    _post_ok("/integrations/partners/tick")
    ok2 = _post_ok("/integrations/partners/mock_echo/call", {"op": "echo", "payload": {"payload": "c"}})
    assert ok2["status"] == "ok" and ok2["rate_remaining"] == 0
    st = _get_ok("/integrations/partners/mock_echo/stats")
    assert st["calls"] >= 2 and st["rate_limited"] >= 1


def test_retry_backoff_and_success_after_failures():
    _patch_ok("/integrations/partners/mock_echo/policy", {"retry_max": 3, "backoff_ms": 25})
    _post_ok("/integrations/partners/mock_echo/reset")
    res = _post_ok("/integrations/partners/mock_echo/call", {"op": "fail_n_times", "payload": {"n": 2}})
    assert res["status"] == "ok"
    assert res["retried"] == 2
    assert res["backoff_ms"] == 50


def test_circuit_breaker_opens_and_reset_closes():
    _patch_ok("/integrations/partners/mock_echo/policy", {"retry_max": 1, "circuit_threshold": 2})
    _post_ok("/integrations/partners/mock_echo/reset")
    # Cause 2 consecutive failures (retry_max=1 means single attempt)
    _post_400("/integrations/partners/mock_echo/call", {"op": "fail_n_times", "payload": {"n": 1}})
    _post_400("/integrations/partners/mock_echo/call", {"op": "fail_n_times", "payload": {"n": 1}})
    # Now circuit should be open and short-circuit further calls
    fast = _post_400("/integrations/partners/mock_echo/call", {"op": "echo"})
    assert fast["status"] == "circuit_open"
    _post_ok("/integrations/partners/mock_echo/reset")
    ok = _post_ok("/integrations/partners/mock_echo/call", {"op": "echo"})
    assert ok["status"] == "ok"


def test_idempotency_dedup_and_no_token_consumption():
    _patch_ok("/integrations/partners/mock_echo/policy", {"rate_limit": 2, "window_tokens": 2})
    _post_ok("/integrations/partners/mock_echo/reset")
    # First call with idempotency key consumes a token
    res1 = _post_ok("/integrations/partners/mock_echo/call", {"op": "echo", "payload": {"x": 1}, "idempotency_key": "k1"})
    rem1 = res1["rate_remaining"]
    # Repeat with same key should dedupe and not consume tokens
    res2 = _post_ok("/integrations/partners/mock_echo/call", {"op": "echo", "payload": {"x": 999}, "idempotency_key": "k1"})
    assert res2["status"] == "ok"
    assert res2["rate_remaining"] == rem1  # unchanged
    st = _get_ok("/integrations/partners/mock_echo/stats")
    assert st["deduped"] >= 1


def test_ui_entry_and_page_have_integrations_controls():
    # /ui should include link to integrations page once implemented
    h = httpx.get(f"{BASE}/ui", timeout=60)
    h.raise_for_status()
    html = h.text
    assert "/ui/integrations" in html
    page = httpx.get(f"{BASE}/ui/integrations", timeout=60)
    page.raise_for_status()
    txt = page.text
    assert "Partners" in txt and "Tick" in txt and "Call" in txt
