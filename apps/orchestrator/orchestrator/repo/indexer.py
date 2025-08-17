from __future__ import annotations

import os
import json
from typing import Dict, Any


def _workspace_root() -> str:
    # Resolve to repo root even when running from different CWDs
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "apps", "orchestrator")):
        return cwd
    # Heuristic: locate repo root by walking up until README.md or docker-compose.yml
    cur = cwd
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "docker-compose.yml")) or os.path.exists(os.path.join(cur, "README.md")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return cwd


def _list_files(base: str) -> list[str]:
    # Deterministic traversal; exclude common large/irrelevant dirs
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv"}
    files: list[str] = []
    for root, dirs, fnames in os.walk(base):
        # in-place filter
        dirs[:] = [d for d in sorted(dirs) if d not in skip_dirs]
        for f in sorted(fnames):
            if f.startswith('.'):
                continue
            path = os.path.join(root, f)
            # Limit to our repo paths only
            files.append(os.path.relpath(path, base))
    return files


def build_repo_map(*, seed: int = 123) -> Dict[str, Any]:
    """
    Offline, deterministic indexer for the local workspace.
    Produces a stable JSON blob with:
      - files: list of tracked files (subset by extensions)
      - modules: per-file summary { language, lines, size_bytes }
      - intents: heuristic tags based on path (api, tests, docs, scripts)
    This keeps M1/M2 tests deterministic without AST heaviness.
    """
    base = _workspace_root()
    exts = {".py", ".md", ".json", ".sh"}
    files = [p for p in _list_files(base) if os.path.splitext(p)[1] in exts]
    modules: Dict[str, Any] = {}
    for rel in files:
        full = os.path.join(base, rel)
        try:
            with open(full, "rb") as f:
                content = f.read()
        except Exception:
            content = b""
        size = len(content)
        line_count = content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)
        ext = os.path.splitext(rel)[1]
        lang = {".py": "python", ".md": "markdown", ".json": "json", ".sh": "shell"}.get(ext, "other")
        intents = []
        if rel.startswith("apps/orchestrator/orchestrator/api/"):
            intents.append("api")
        if rel.startswith("apps/orchestrator/tests/"):
            intents.append("tests")
        if rel.startswith("docs/"):
            intents.append("docs")
        if rel.startswith("scripts/"):
            intents.append("scripts")
        modules[rel] = {"language": lang, "lines": line_count, "size_bytes": size, "intents": sorted(intents)}

    # stable ordering of keys for reproducibility
    out = {
        "version": 1,
        "seed": int(seed),
        "files": sorted(files),
        "modules": {k: modules[k] for k in sorted(modules.keys())},
    }
    # Validate JSON-serializable and stable
    json.dumps(out, sort_keys=True)
    return out


def compute_hotspots(repo_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic heuristic hotspots: large and highly-edited areas.
    We approximate edit density by weighting tests/docs lower and code higher.
    """
    mods = repo_map.get("modules", {}) if isinstance(repo_map, dict) else {}
    hotspots: list[dict] = []
    for path in sorted(mods.keys()):
        m = mods[path]
        weight = m.get("lines", 0)
        intents = set(m.get("intents", []))
        if "tests" in intents:
            weight = max(1, weight // 4)
        if "docs" in intents:
            weight = max(1, weight // 8)
        hotspots.append({"path": path, "score": int(weight)})
    # sort desc by score, then path
    hotspots.sort(key=lambda x: (-x["score"], x["path"]))
    return {
        "version": 1,
        "hotspots": hotspots,
    }


