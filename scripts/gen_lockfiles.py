#!/usr/bin/env python3
"""
Deterministic, local-only lockfile generator.

Inputs:
- apps/orchestrator/requirements.txt
- requirements-dev.txt (may include -r lines)

Outputs (overwritten idempotently):
- apps/orchestrator/requirements.lock.txt
- requirements-dev.lock.txt

Rules:
- Fail on any unpinned specifiers (>=, >, <, !=, ~=, *, no version, VCS/URLs)
- Normalize to name==version only (extras removed, name lowercased)
- Sorted, unique by name, newline-terminated
- No network calls
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUTS: Tuple[Path, Path] = (
    REPO_ROOT / "apps" / "orchestrator" / "requirements.txt",
    REPO_ROOT / "requirements-dev.txt",
)

PINNED_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9_.\-]+)(?P<extras>\[[^\]]+\])?==(?P<version>[^#\s]+)$")


class LockfileError(Exception):
    pass


def read_requirements(path: Path, seen: Set[Path] | None = None) -> List[str]:
    if seen is None:
        seen = set()
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    if not path.exists():
        raise LockfileError(f"Requirements file not found: {path}")
    lines: List[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("-r ") or line.lower().startswith("--requirement "):
            ref = line.split(maxsplit=1)[1].strip()
            ref_path = (REPO_ROOT / ref).resolve()
            lines.extend(read_requirements(ref_path, seen))
            continue
        lines.append(line)
    return lines


def ensure_pinned(req_lines: Iterable[str]) -> Dict[str, str]:
    name_to_version: Dict[str, str] = {}
    for line in req_lines:
        if any(prefix in line for prefix in ("git+", "http://", "https://", "file://")):
            raise LockfileError(f"VCS/URL dependencies are not allowed: {line}")
        m = PINNED_PATTERN.match(line)
        if not m:
            # Provide clearer message if common specifiers are found
            if any(op in line for op in (">=", ">", "<", "!=", "~=", "*")) or "==" not in line:
                raise LockfileError(
                    f"Unpinned or invalid specifier detected: {line} | Expected pinned format: name==version"
                )
            raise LockfileError(f"Invalid requirement format: {line}")
        name = m.group("name").lower()
        version = m.group("version")
        if name in name_to_version and name_to_version[name] != version:
            raise LockfileError(
                f"Conflicting versions for {name}: {name_to_version[name]} vs {version}"
            )
        name_to_version[name] = version
    return name_to_version


def write_lockfile(output_path: Path, name_to_version: Dict[str, str]) -> None:
    lines = [f"{name}=={version}" for name, version in sorted(name_to_version.items())]
    content = "\n".join(lines) + "\n"
    # Idempotent write: only touch file if content changes
    if output_path.exists():
        current = output_path.read_text()
        if current == content:
            return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)


def build_lock(inputs: List[Path]) -> None:
    for input_path in inputs:
        reqs = read_requirements(input_path)
        name_to_version = ensure_pinned(reqs)
        lock_path = input_path.with_suffix(".lock.txt")
        write_lockfile(lock_path, name_to_version)


def main(argv: List[str]) -> int:
    if os.environ.get("SUPPLY_CHAIN_ENABLED", "1") != "1":
        print("Supply chain checks disabled via SUPPLY_CHAIN_ENABLED=0", file=sys.stderr)
        return 0
    inputs = list(DEFAULT_INPUTS)
    try:
        build_lock(inputs)
    except LockfileError as e:
        print(f"[gen_lockfiles] ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


