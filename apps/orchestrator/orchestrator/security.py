import re
from pathlib import Path
from typing import Iterator, List, Dict, Tuple


_SECRET_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("aws_secret_access_key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*([A-Za-z0-9/+=]{40})")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("password_assignment", re.compile(r"(?i)(?:password|passwd|pwd)\s*[:=]\s*([^\s#'\"]{8,})")),
]


def _is_probably_binary(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    # Heuristic: proportion of non-text bytes
    text_bytes = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = sum(1 for b in sample if b not in text_bytes)
    return (nontext / max(1, len(sample))) > 0.30


def _iter_text_files(root: Path) -> Iterator[Path]:
    skip_dirs = {
        ".git",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
    }
    for path in root.rglob("*"):
        if path.is_dir():
            # Skip heavy/irrelevant directories
            continue
        # Explicit exclusions
        if path.name == "dev.db":
            continue
        # Skip files under excluded directories
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            with path.open("rb") as f:
                sample = f.read(4096)
            if _is_probably_binary(sample):
                continue
        except Exception:
            # Unreadable files are skipped
            continue
        yield path


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    start = value[:4]
    end = value[-4:]
    return f"{start}***{end}"


def _scan_text(path: Path, text: str) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    lines = text.splitlines()
    # Additional .pem heuristic: filename suggests key material
    pem_hint = path.suffix.lower() == ".pem"
    for idx, line in enumerate(lines, start=1):
        if pem_hint and "-----BEGIN" in line:
            findings.append({
                "file": str(path),
                "line": idx,
                "kind": "pem_key_material",
                "excerpt": line.strip()[:120],
            })
        for kind, pat in _SECRET_PATTERNS:
            for m in pat.finditer(line):
                val = m.group(0)
                masked = _mask_secret(val)
                findings.append({
                    "file": str(path),
                    "line": idx,
                    "kind": kind,
                    "excerpt": line.strip()[:200].replace(val, masked),
                })
    return findings


def scan_for_secrets(root_path: str) -> List[Dict[str, object]]:
    """
    Deterministic, local-only secret scanner.
    - Scans text files under root_path recursively
    - Skips likely binaries and 'dev.db'
    - Detects common high-risk patterns and returns findings with file/line
    """
    root = Path(root_path).resolve()
    results: List[Dict[str, object]] = []
    for path in _iter_text_files(root):
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        results.extend(_scan_text(path, text))
    return results


def enforce_policy(root_path: str) -> List[Dict[str, object]]:
    """
    Policy gate: returns list of blocking findings. Empty list means clean.
    """
    return scan_for_secrets(root_path)


