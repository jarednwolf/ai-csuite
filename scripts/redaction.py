#!/usr/bin/env python3
import sys, os
from typing import Any

# Reuse orchestrator redaction implementation for single source of truth
_APPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "orchestrator"))
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)
from orchestrator.security import apply_redaction as _apply_redaction  # type: ignore
from orchestrator.security import mask_dict as _mask_dict  # type: ignore


def apply_redaction(text: str, mode: str = "strict") -> str:
    return _apply_redaction(text, mode=mode)


def mask_dict(obj: Any, mode: str = "strict") -> Any:
    return _mask_dict(obj, mode=mode)


def _main() -> int:
    data = sys.stdin.read()
    mode = (sys.argv[1] if len(sys.argv) > 1 else "strict").strip()
    sys.stdout.write(apply_redaction(data, mode=mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


