from __future__ import annotations

import time
from typing import Dict, Any


def run_speculation(*, description: str, seed: int = 123) -> Dict[str, Any]:
    """
    Deterministic speculative execution stub.
    Simulates building a sandbox image and running smoke/eval suites with a seeded RNG.
    Offline only; returns a risk score and stable metrics.
    """
    started = int(time.time())
    # Stable, pseudo-random but deterministic metrics from seed
    risk = (seed % 7) / 10.0  # 0.0 .. 0.6
    tests = {"total": 10, "passed": 10 - (seed % 3), "failed": (seed % 3)}
    evals = {"score": round(0.8 - (seed % 5) * 0.01, 2)}
    costs = {"cpu_sec": 3 + (seed % 3), "io_mb": 5 + (seed % 4)}
    report = {
        "version": 1,
        "description": description,
        "seed": int(seed),
        "started_ts": started,
        "metrics": {"risk": risk, "tests": tests, "evals": evals, "costs": costs},
        "status": "ok" if tests["failed"] == 0 else "warn",
    }
    return report


