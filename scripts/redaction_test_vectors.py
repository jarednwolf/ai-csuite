#!/usr/bin/env python3
import json
import os
from typing import List, Dict

from redaction import apply_redaction


def main() -> int:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vectors_path = os.path.join(base, "compliance", "test_vectors.json")
    report_path = os.path.join(base, "compliance", "redaction_report.json")

    try:
        with open(vectors_path, "r", encoding="utf-8") as f:
            vectors: List[Dict] = json.load(f)
    except FileNotFoundError:
        print("missing compliance/test_vectors.json", flush=True)
        return 1

    report: Dict[str, Dict] = {}
    failed = False
    for v in vectors:
        vid = str(v.get("id"))
        inp = v.get("input", "")
        exp_strict = v.get("expect_strict", "")
        exp_relaxed = v.get("expect_relaxed", "")
        out_strict = apply_redaction(inp, mode="strict")
        out_relaxed = apply_redaction(inp, mode="relaxed")
        ok_s = (out_strict == exp_strict)
        ok_r = (out_relaxed == exp_relaxed)
        if not (ok_s and ok_r):
            failed = True
        report[vid] = {
            "input": inp,
            "out_strict": out_strict,
            "out_relaxed": out_relaxed,
            "expect_strict": exp_strict,
            "expect_relaxed": exp_relaxed,
            "ok_strict": ok_s,
            "ok_relaxed": ok_r,
        }

    # Deterministic write
    os.makedirs(os.path.join(base, "compliance"), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


