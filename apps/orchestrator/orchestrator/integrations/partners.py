from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except Exception:
        return default


def _env_true(key: str, default: str = "1") -> bool:
    try:
        v = os.getenv(key, default).strip().lower()
    except Exception:
        v = default
    return v not in {"0", "false", "no"}


@dataclass
class PartnerPolicy:
    rate_limit: int = 60
    retry_max: int = 3
    backoff_ms: int = 0
    circuit_threshold: int = 5
    window_tokens: int = 60

    @classmethod
    def from_env(cls) -> "PartnerPolicy":
        return cls(
            rate_limit=_env_int("PARTNER_RATE_LIMIT", 60),
            retry_max=_env_int("PARTNER_RETRY_MAX", 3),
            backoff_ms=_env_int("PARTNER_BACKOFF_MS", 0),
            circuit_threshold=_env_int("PARTNER_CIRCUIT_THRESHOLD", 5),
            window_tokens=_env_int("PARTNER_WINDOW_TOKENS", 60),
        )


@dataclass
class PartnerCounters:
    calls: int = 0
    retries: int = 0
    rate_limited: int = 0
    deduped: int = 0
    failures: int = 0
    circuit_open: int = 0


@dataclass
class PartnerState:
    tokens: int
    circuit_state: str = "closed"  # "closed" | "open"
    consecutive_failures: int = 0
    counters: PartnerCounters = field(default_factory=PartnerCounters)
    idempotency_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class PartnerOpError(Exception):
    pass


class PartnerAdapter:
    def id(self) -> str:
        raise NotImplementedError

    def call(self, op: str, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        raise NotImplementedError


class MockEchoAdapter(PartnerAdapter):
    """
    Deterministic in-process mock adapter.
    Ops:
      - echo: returns the payload
      - fail_n_times: fails N times for the same _call_id then succeeds
        Payload contract (internal keys are injected by service):
          { "n": <int>, "_call_id": <uuid>, "_attempt": <int> }
    """

    def __init__(self) -> None:
        self._inflight_failures: Dict[str, int] = {}

    def id(self) -> str:
        return "mock_echo"

    def call(self, op: str, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        p = dict(payload or {})
        if op == "echo":
            return {"echo": p.get("payload", p)}

        if op == "fail_n_times":
            call_id = str(p.get("_call_id") or "")
            attempt = int(p.get("_attempt") or 0)
            n = int(p.get("n") or 0)
            if call_id:
                if attempt == 0:
                    # Initialize remaining failures for this call
                    self._inflight_failures[call_id] = max(0, n)
                remaining = self._inflight_failures.get(call_id, 0)
                if remaining > 0:
                    self._inflight_failures[call_id] = remaining - 1
                    raise PartnerOpError("injected failure")
                # Success, clean up
                self._inflight_failures.pop(call_id, None)
            else:
                # If no call id provided, be conservative and never fail
                pass
            return {"ok": True, "attempt": attempt, "injected_failures": n}

        raise PartnerOpError(f"unsupported op: {op}")


@dataclass
class _Entry:
    adapter: PartnerAdapter
    policy: PartnerPolicy
    state: PartnerState


_ENABLED = _env_true("PARTNER_ENABLED", "1")


def _initial_tokens(pol: PartnerPolicy) -> int:
    # Capacity equals rate_limit; initial fill is min(window_tokens, rate_limit)
    return max(0, min(pol.window_tokens, pol.rate_limit))


_REGISTRY: Dict[str, _Entry] = {}


def _ensure_registry() -> None:
    global _REGISTRY
    if _REGISTRY:
        return
    if not _ENABLED:
        _REGISTRY = {}
        return
    default_policy = PartnerPolicy.from_env()
    # Register built-in mock adapter
    for ad in [MockEchoAdapter()]:
        pol = PartnerPolicy(
            rate_limit=default_policy.rate_limit,
            retry_max=default_policy.retry_max,
            backoff_ms=default_policy.backoff_ms,
            circuit_threshold=default_policy.circuit_threshold,
            window_tokens=default_policy.window_tokens,
        )
        st = PartnerState(tokens=_initial_tokens(pol))
        _REGISTRY[ad.id()] = _Entry(adapter=ad, policy=pol, state=st)


def list_partners() -> List[Dict[str, Any]]:
    _ensure_registry()
    items: List[Tuple[str, _Entry]] = sorted(_REGISTRY.items(), key=lambda kv: kv[0])
    out: List[Dict[str, Any]] = []
    for pid, e in items:
        out.append({
            "partner_id": pid,
            "policy": policy_for(pid),
            "state": {
                "rate_remaining": e.state.tokens,
                "circuit_state": e.state.circuit_state,
            },
            "counters": stats_for(pid),
        })
    return out


def _get(pid: str) -> _Entry:
    _ensure_registry()
    if pid not in _REGISTRY:
        raise KeyError("partner not found")
    return _REGISTRY[pid]


def policy_for(pid: str) -> Dict[str, int]:
    e = _get(pid)
    p = e.policy
    return {
        "rate_limit": int(p.rate_limit),
        "retry_max": int(p.retry_max),
        "backoff_ms": int(p.backoff_ms),
        "circuit_threshold": int(p.circuit_threshold),
        "window_tokens": int(p.window_tokens),
    }


def patch_policy(pid: str, patch: Dict[str, Any]) -> Dict[str, int]:
    e = _get(pid)
    p = e.policy
    if isinstance(patch.get("rate_limit"), int):
        p.rate_limit = max(0, int(patch["rate_limit"]))  # type: ignore[index]
    if isinstance(patch.get("retry_max"), int):
        p.retry_max = max(0, int(patch["retry_max"]))  # type: ignore[index]
    if isinstance(patch.get("backoff_ms"), int):
        p.backoff_ms = max(0, int(patch["backoff_ms"]))  # type: ignore[index]
    if isinstance(patch.get("circuit_threshold"), int):
        p.circuit_threshold = max(1, int(patch["circuit_threshold"]))  # type: ignore[index]
    if isinstance(patch.get("window_tokens"), int):
        p.window_tokens = max(0, int(patch["window_tokens"]))  # type: ignore[index]
    # Ensure tokens do not exceed capacity
    e.state.tokens = min(e.state.tokens, p.rate_limit)
    return policy_for(pid)


def stats_for(pid: str) -> Dict[str, int]:
    e = _get(pid)
    c = e.state.counters
    return {
        "calls": int(c.calls),
        "retries": int(c.retries),
        "rate_limited": int(c.rate_limited),
        "deduped": int(c.deduped),
        "failures": int(c.failures),
        "circuit_open": int(c.circuit_open),
    }


def reset_partner(pid: str) -> Dict[str, Any]:
    e = _get(pid)
    e.state = PartnerState(tokens=_initial_tokens(e.policy))
    return {
        "partner_id": pid,
        "policy": policy_for(pid),
        "state": {"rate_remaining": e.state.tokens, "circuit_state": e.state.circuit_state},
        "counters": stats_for(pid),
    }


def tick_all() -> Dict[str, Any]:
    _ensure_registry()
    for pid, e in _REGISTRY.items():
        # Deterministic refill to full capacity each tick
        e.state.tokens = int(e.policy.rate_limit)
    return {
        "status": "ok",
        "partners": [
            {"partner_id": pid, "rate_remaining": e.state.tokens, "circuit_state": e.state.circuit_state}
            for pid, e in sorted(_REGISTRY.items(), key=lambda kv: kv[0])
        ],
    }


def call_partner(
    pid: str,
    *,
    op: str,
    payload: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    e = _get(pid)
    st = e.state
    pol = e.policy

    # Idempotency fast-path
    if idempotency_key and idempotency_key in st.idempotency_cache:
        st.counters.deduped += 1
        cached = st.idempotency_cache[idempotency_key]
        # Return a shallow copy to prevent accidental mutation
        resp = dict(cached)
        return True, resp

    # Circuit breaker short-circuit
    if st.circuit_state == "open":
        st.counters.circuit_open += 1
        return False, {
            "status": "circuit_open",
            "retried": 0,
            "backoff_ms": 0,
            "rate_remaining": st.tokens,
            "circuit_state": st.circuit_state,
            "error": "circuit breaker is open",
        }

    # Rate limit check (do not decrement here; decrement on success)
    if st.tokens <= 0:
        st.counters.rate_limited += 1
        return False, {
            "status": "rate_limited",
            "retried": 0,
            "backoff_ms": 0,
            "rate_remaining": st.tokens,
            "circuit_state": st.circuit_state,
            "error": "rate limit exceeded",
        }
    # Count the call now; token will be decremented only on success
    st.counters.calls += 1

    # Attempt with deterministic retry/backoff (tracked only)
    retried = 0
    backoff_ms = 0
    call_id = str(uuid.uuid4())
    last_err: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    for attempt in range(0, max(1, pol.retry_max)):
        try:
            # Adapter payload is augmented with internal call metadata
            augmented = dict(payload or {})
            augmented.setdefault("_call_id", call_id)
            augmented.setdefault("_attempt", attempt)
            res = e.adapter.call(op, augmented)
            result = res if isinstance(res, dict) else {"result": res}
            # Success; reset failure streak
            st.consecutive_failures = 0
            # Consume one token for a successful call
            if st.tokens > 0:
                st.tokens -= 1
            break
        except PartnerOpError as ex:
            last_err = str(ex)
            if attempt + 1 >= pol.retry_max:
                # Exhausted
                result = None
                st.counters.failures += 1
                st.consecutive_failures += 1
                if st.consecutive_failures >= pol.circuit_threshold:
                    st.circuit_state = "open"
                break
            # Track retry
            retried += 1
            st.counters.retries += 1
            backoff_ms += max(0, pol.backoff_ms)
            # continue loop without sleeping

    if result is not None:
        resp = {
            "status": "ok",
            "result": result,
            "retried": retried,
            "backoff_ms": backoff_ms,
            "rate_remaining": st.tokens,
            "circuit_state": st.circuit_state,
        }
        if idempotency_key:
            st.idempotency_cache[idempotency_key] = dict(resp)
        return True, resp

    # Failure path (HTTP 400 expected by endpoint)
    return False, {
        "status": "failed",
        "error": last_err or "operation failed",
        "retried": retried,
        "backoff_ms": backoff_ms,
        "rate_remaining": st.tokens,
        "circuit_state": st.circuit_state,
    }



