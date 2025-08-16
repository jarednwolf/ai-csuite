#!/usr/bin/env python3
"""
Local SBOM generator using only stdlib importlib.metadata.
Outputs JSON to sbom/orchestrator-packages.json with deterministic ordering.
No network calls. Idempotent: re-runs produce identical output if environment unchanged.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SBOM_DIR = REPO_ROOT / "sbom"
OUTPUT = SBOM_DIR / "orchestrator-packages.json"


def iso_utc_now() -> str:
    # Deterministic format, UTC timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def collect_packages() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for dist in importlib_metadata.distributions():
        name = dist.metadata.get("Name") or dist.metadata.get("Summary") or dist.metadata.get("name")
        version = dist.metadata.get("Version") or dist.version
        summary = dist.metadata.get("Summary") or ""
        if not name or not version:
            # Skip invalid distributions
            continue
        items.append({
            "name": str(name),
            "version": str(version),
            "summary": str(summary),
        })
    items.sort(key=lambda x: (x["name"].lower(), x["version"]))
    return items


def main(argv: List[str]) -> int:
    if os.environ.get("SUPPLY_CHAIN_ENABLED", "1") != "1":
        print("Supply chain checks disabled via SUPPLY_CHAIN_ENABLED=0", file=sys.stderr)
        return 0

    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    # Reuse prior generated_at to keep idempotent output if inputs unchanged
    prior_generated_at: str | None = None
    if OUTPUT.exists():
        try:
            prior = json.loads(OUTPUT.read_text())
            prior_generated_at = prior.get("metadata", {}).get("generated_at")
        except Exception:
            prior_generated_at = None

    payload: Dict[str, Any] = {
        "metadata": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "generated_at": prior_generated_at or iso_utc_now(),
        },
        "packages": collect_packages(),
    }
    content = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    # Idempotent write
    if OUTPUT.exists():
        current = OUTPUT.read_text()
        if current == content:
            return 0
    OUTPUT.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


