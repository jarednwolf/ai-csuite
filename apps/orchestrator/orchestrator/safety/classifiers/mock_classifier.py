from __future__ import annotations

from typing import Mapping


def classify(text: str) -> Mapping[str, float]:
    # Deterministic toy classifier: returns fixed categories by keyword
    lower = (text or "").lower()
    return {
        "toxicity": 1.0 if "toxic" in lower else 0.0,
        "violence": 1.0 if "violence" in lower else 0.0,
        "sexual": 1.0 if "nsfw" in lower else 0.0,
    }



