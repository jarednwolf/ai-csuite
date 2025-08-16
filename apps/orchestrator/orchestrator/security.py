import os
import re
import uuid
import json
from pathlib import Path
from typing import Iterator, List, Dict, Tuple, Any, Optional

from sqlalchemy.orm import Session

from .models import AuditLog


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


# ---------------- Phase 23: Redaction helpers ----------------

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_NAME_SEQ_RE = re.compile(r"\b(?:[A-Z][a-z]{1,})(?:\s+[A-Z][a-z]{1,}){1,}\b")

def _luhn_ok(s: str) -> bool:
    digits = [int(c) for c in re.sub(r"[^0-9]", "", s)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def apply_redaction(text: str, mode: str = "strict") -> str:
    """
    Deterministic redaction for logs/prompts/markdown.
    Modes:
      - strict: redact emails, phone, IP, SSN, valid credit cards (Luhn), name heuristics, common secret tokens
      - relaxed: redact only emails, SSN, valid credit cards
    """
    s = text or ""
    # Always redact emails
    s = _EMAIL_RE.sub("<email:redacted>", s)

    if mode == "strict":
        s = _PHONE_RE.sub("<phone:redacted>", s)
        s = _IP_RE.sub("<ip:redacted>", s)
        s = _SSN_RE.sub("<ssn:redacted>", s)
        # Credit cards with Luhn
        def _cc_sub(m: re.Match[str]) -> str:
            val = m.group(0)
            return "<cc:redacted>" if _luhn_ok(val) else val
        s = _CC_RE.sub(_cc_sub, s)
        # Names heuristics: redact the last two capitalized tokens in a sequence of 2+ capitalized words
        def _name_sub(m: re.Match[str]) -> str:
            seq = m.group(0)
            parts = seq.split()
            if len(parts) <= 2:
                return "<name:redacted>"
            # Preserve prefix words (e.g., Hello), redact trailing first and last name
            return " ".join(parts[:-2]) + " <name:redacted>"
        s = _NAME_SEQ_RE.sub(_name_sub, s)
        # Common secret formats
        s = re.sub(r"ghp_[A-Za-z0-9]{20,}", "ghp_<redacted>", s)
        s = re.sub(r"(?i)aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{40}", "aws_secret_access_key=<redacted>", s)
        s = re.sub(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "<pem:redacted>", s)
        s = re.sub(r"(?i)(password|passwd|pwd)\s*[:=]\s*([^\s#'\"]{4,})", r"\1=<redacted>", s)
    else:
        # relaxed
        s = _SSN_RE.sub("<ssn:redacted>", s)
        def _cc_sub2(m: re.Match[str]) -> str:
            val = m.group(0)
            return "<cc:redacted>" if _luhn_ok(val) else val
        s = _CC_RE.sub(_cc_sub2, s)
    return s


def mask_dict(obj: Any, mode: str = "strict") -> Any:
    """Recursively apply apply_redaction to all string leaves.
    Deterministic traversal (sort keys where applicable).
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        return apply_redaction(obj, mode=mode)
    if isinstance(obj, list):
        return [mask_dict(x, mode=mode) for x in obj]
    if isinstance(obj, tuple):
        return tuple(mask_dict(x, mode=mode) for x in obj)
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            out[k] = mask_dict(obj[k], mode=mode)
        return out
    return obj


def _env_true(key: str, default: str = "1") -> bool:
    try:
        v = os.getenv(key, default).strip().lower()
    except Exception:
        v = default
    return v not in {"0", "false", "no"}


def safe_log(message: str, *, context: Optional[Dict[str, Any]] = None, mode: str = "strict") -> str:
    """
    Centralized redaction for application logs. Returns a redacted line for structured logging.
    """
    ctx = mask_dict(context or {}, mode=mode)
    payload = {"message": apply_redaction(message or "", mode=mode), "context": ctx}
    # Tie to deterministic JSON encoding for tests
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


# ---------------- Phase 23: Audit logging ----------------

def _audit_enabled() -> bool:
    return _env_true("AUDIT_ENABLED", "1")


def audit_event(
    db: Session,
    *,
    actor: str,
    event_type: str,
    run_id: Optional[str] = None,
    project_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    redaction_mode: Optional[str] = None,
) -> Optional[str]:
    """
    Append-only audit log with idempotency on (event_type, run_id, request_id).
    Inputs are redacted via mask_dict.
    Returns audit id or None when disabled.
    """
    if not _audit_enabled():
        return None
    req_id = (request_id or "")[:64]
    red_mode = redaction_mode or os.getenv("REDACTION_MODE", "strict")
    red_details = mask_dict(details or {}, mode=red_mode)
    # Idempotent insert: rely on unique constraint and ignore on conflict
    try:
        row = AuditLog(
            id=str(uuid.uuid4()),
            actor=(actor or "system")[:64],
            event_type=(event_type or "")[:64],
            run_id=(run_id or None),
            project_id=(project_id or None),
            request_id=req_id,
            details_redacted=red_details,
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        # Likely duplicate due to UniqueConstraint; treat as idempotent success
        return None


