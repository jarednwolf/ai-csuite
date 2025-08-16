#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Rule:
    id: str
    category: str  # secret|pii
    severity: str  # block|warn
    description: str
    pattern: str
    redaction: str


def _load_rules(path: Path) -> List[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules: List[Rule] = []
    for r in data:
        rules.append(Rule(
            id=str(r.get("id")),
            category=str(r.get("category")),
            severity=str(r.get("severity")),
            description=str(r.get("description")),
            pattern=str(r.get("pattern")),
            redaction=str(r.get("redaction")),
        ))
    return rules


def _is_probably_binary(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    text_bytes = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = sum(1 for b in sample if b not in text_bytes)
    return (nontext / max(1, len(sample))) > 0.30


def _iter_text_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        # Respect .gitignore? Simplified: skip common dirs explicitly
        parts = set(p.parts)
        if {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"} & parts:
            continue
        if p.name == "dev.db":
            continue
        try:
            with p.open("rb") as f:
                sample = f.read(4096)
            if _is_probably_binary(sample):
                continue
        except Exception:
            continue
        out.append(p)
    out.sort(key=lambda x: str(x))
    return out


def _match_globs(path: str, globs: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _compile_patterns(rules: List[Rule]):
    import re
    compiled = []
    for r in rules:
        compiled.append((r, re.compile(r.pattern)))
    return compiled


def run_scan(root_dir: str, include: List[str], exclude: List[str], rules_path: str, allow_warn_override: bool) -> Tuple[int, Dict]:
    root = Path(root_dir).resolve()
    rules = _load_rules(Path(rules_path))
    compiled = _compile_patterns(rules)
    findings: Dict[str, Dict] = {}
    for file_path in _iter_text_files(root):
        rel = os.path.relpath(str(file_path), str(root))
        # include/exclude
        if include and not _match_globs(rel, include):
            continue
        if exclude and _match_globs(rel, exclude):
            continue
        try:
            text = file_path.read_text(errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines, start=1):
            for r, pat in compiled:
                for m in pat.finditer(line):
                    key = f"{rel}:{idx}:{r.category}:{r.id}"
                    if key in findings:
                        continue
                    # Replace only the match with redaction token
                    red_line = line[:m.start()] + r.redaction + line[m.end():]
                    findings[key] = {
                        "file": rel,
                        "line": idx,
                        "category": r.category,
                        "severity": r.severity,
                        "rule_id": r.id,
                        "description": r.description,
                        "excerpt": red_line[:200],
                    }

    # Deterministic ordering by key
    ordered_keys = sorted(findings.keys())
    report = {k: findings[k] for k in ordered_keys}
    # Exit code rules
    has_block = any(v.get("severity") == "block" for v in report.values())
    if has_block:
        exit_code = 1
    else:
        exit_code = 0
    if allow_warn_override:
        exit_code = 0 if not has_block else 1
    return exit_code, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--rules", default="compliance/regexes.json")
    ap.add_argument("--include", default=os.getenv("SECRETS_SCAN_INCLUDE", ""))
    ap.add_argument("--exclude", default=os.getenv("SECRETS_SCAN_EXCLUDE", ""))
    ap.add_argument("--out", default="compliance/secrets_report.json")
    ap.add_argument("--allow-warn-override", action="store_true", default=os.getenv("COMPLIANCE_ALLOW_WARN_OVERRIDE", "0") in {"1","true","yes"})
    args = ap.parse_args()

    include = [x.strip() for x in (args.include.split(",") if args.include else []) if x.strip()]
    exclude = [x.strip() for x in (args.exclude.split(",") if args.exclude else []) if x.strip()]

    code, report = run_scan(args.root, include, exclude, args.rules, args.allow_warn_override)
    # Deterministic write
    base = Path(args.out).parent
    base.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())


