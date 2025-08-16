#!/usr/bin/env python3
"""
Local license allowlist checker using importlib.metadata only.
Writes deterministic report to sbom/licenses.json and exits non-zero on violations.

Environment:
- LICENSE_ALLOWLIST: comma-separated list; defaults provided below
- SUPPLY_CHAIN_ALLOW_UNKNOWN: if '1', unknown licenses are allowed
- SUPPLY_CHAIN_ENABLED: if '0', script exits 0 and does nothing
"""

from __future__ import annotations

import json
import os
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SBOM_DIR = REPO_ROOT / "sbom"
OUTPUT = SBOM_DIR / "licenses.json"

DEFAULT_ALLOWLIST = {
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "PSF",
    "MPL-2.0",
    # Common variants to avoid false negatives while staying permissive
    "BSD",  # maps generic BSD License classifiers
    "LGPL-3.0",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "LGPL-2.1",
    "LGPL-2.1-or-later",
    "LGPL",
}


def parse_allowlist() -> List[str]:
    env_val = os.environ.get("LICENSE_ALLOWLIST", "")
    if not env_val.strip():
        return sorted(DEFAULT_ALLOWLIST)
    return sorted([s.strip() for s in env_val.split(",") if s.strip()])


def best_license_for_dist(dist: importlib_metadata.Distribution) -> Tuple[str, List[str]]:
    md = dist.metadata
    declared = md.get("License") or ""
    classifiers = [c for c in md.get_all("Classifier") or [] if c.startswith("License :: ")]
    # Try to extract short IDs from classifiers, e.g., "License :: OSI Approved :: MIT License"
    short_from_classifiers: List[str] = []
    classifier_map = {
        "MIT License": "MIT",
        "Apache Software License": "Apache-2.0",
        "BSD License": "BSD-3-Clause",
        "GNU Lesser General Public License v3": "LGPL-3.0-or-later",
        "GNU Lesser General Public License v2.1": "LGPL-2.1-or-later",
        "Mozilla Public License 2.0": "MPL-2.0",
        "Python Software Foundation License": "PSF",
        "ISC License": "ISC",
    }
    for c in classifiers:
        for fragment, canonical in classifier_map.items():
            if fragment in c:
                short_from_classifiers.append(canonical)
    short_from_classifiers = sorted(set(short_from_classifiers))
    license_label = declared.strip() or (short_from_classifiers[0] if short_from_classifiers else "")
    return license_label, short_from_classifiers


def canonicalize_license(label: str, classifier_ids: List[str]) -> str:
    lab = (label or "").strip()
    if lab:
        l = lab.lower()
        if "mit" in l:
            return "MIT"
        if "apache" in l:
            return "Apache-2.0"
        if "bsd" in l:
            # default to 3-clause when unspecified
            return "BSD-3-Clause"
        if "isc" in l:
            return "ISC"
        if "mozilla" in l or "mpl" in l:
            return "MPL-2.0"
        if "python software foundation" in l or l == "psf":
            return "PSF"
        if "lgpl" in l:
            return "LGPL-3.0-or-later"
    # fallback to classifier-derived ids if present
    for cid in classifier_ids:
        if cid in DEFAULT_ALLOWLIST:
            return cid
    return lab


# Fallback known license map for core deps when metadata is incomplete
KNOWN_LICENSES: Dict[str, str] = {
    "langgraph": "MIT",
    "langchain-core": "MIT",
    "fastapi": "MIT",
    "sqlalchemy": "MIT",
    "uvicorn": "BSD-3-Clause",
    "httpx": "BSD-3-Clause",
    "numpy": "BSD-3-Clause",
    "pydantic": "MIT",
    "psycopg": "LGPL-3.0-or-later",
    "pypdf": "BSD-3-Clause",
    "python-dotenv": "BSD-3-Clause",
    "typing-extensions": "PSF",
    "temporalio": "Apache-2.0",
}


def read_target_package_names() -> List[str]:
    # Prefer lockfiles; fallback to requirements files if lockfiles absent
    candidates = [
        REPO_ROOT / "apps/orchestrator/requirements.lock.txt",
        REPO_ROOT / "requirements-dev.lock.txt",
        REPO_ROOT / "apps/orchestrator/requirements.txt",
        REPO_ROOT / "requirements-dev.txt",
    ]
    names: set[str] = set()
    for p in candidates:
        if not p.exists():
            continue
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("-r ") or line.lower().startswith("--requirement "):
                # we will pick up included file directly when encountered in candidates
                continue
            # Accept only pinned-like tokens to extract a name; extras removed
            token = line.split("==")[0].strip()
            token = token.split("[")[0].strip()
            if token:
                names.add(token.lower())
    return sorted(names)


def collect(target_names: List[str]) -> List[Dict[str, Any]]:
    target_set = set(n.lower() for n in target_names)
    rows: List[Dict[str, Any]] = []
    for dist in importlib_metadata.distributions():
        name = (dist.metadata.get("Name") or dist.metadata.get("name") or "").strip()
        version = (dist.metadata.get("Version") or dist.version or "").strip()
        if not name or not version:
            continue
        if target_set and name.lower() not in target_set:
            continue
        license_label, classifiers_ids = best_license_for_dist(dist)
        if (not license_label) and (name.lower() in KNOWN_LICENSES):
            license_label = KNOWN_LICENSES[name.lower()]
        rows.append({
            "name": str(name),
            "version": str(version),
            "license": license_label,
            "classifiers": classifiers_ids,
        })
    rows.sort(key=lambda x: (x["name"].lower(), x["version"]))
    return rows


def main(argv: List[str]) -> int:
    if os.environ.get("SUPPLY_CHAIN_ENABLED", "1") != "1":
        print("Supply chain checks disabled via SUPPLY_CHAIN_ENABLED=0", file=sys.stderr)
        return 0
    allow_unknown = os.environ.get("SUPPLY_CHAIN_ALLOW_UNKNOWN", "0") == "1"
    allowlist = set(s.strip() for s in parse_allowlist() if s.strip())
    SBOM_DIR.mkdir(parents=True, exist_ok=True)
    rows = collect(read_target_package_names())

    violations: List[str] = []
    for row in rows:
        lic = (row.get("license") or "").strip()
        normalized = canonicalize_license(lic, row.get("classifiers") or [])
        if normalized and normalized in allowlist:
            continue
        # Try classifiers-derived IDs
        classifiers: List[str] = row.get("classifiers") or []
        if any(c in allowlist for c in classifiers):
            continue
        if not normalized and allow_unknown:
            continue
        if not normalized:
            violations.append(f"{row['name']}=={row['version']} has unknown license")
        else:
            violations.append(f"{row['name']}=={row['version']} uses disallowed license: {normalized}")

    # Write report deterministically
    content = json.dumps({"allowlist": sorted(list(allowlist)), "packages": rows}, sort_keys=True, indent=2) + "\n"
    if OUTPUT.exists():
        current = OUTPUT.read_text()
        if current != content:
            OUTPUT.write_text(content)
    else:
        OUTPUT.write_text(content)

    if violations:
        print("[license_check] violations detected:", file=sys.stderr)
        for v in violations:
            print(f" - {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


