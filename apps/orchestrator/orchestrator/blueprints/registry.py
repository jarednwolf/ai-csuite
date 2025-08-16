from __future__ import annotations

import json
import os
from typing import Dict, List

from .models import BlueprintManifest, BlueprintSummary, summarize


class BlueprintRegistry:
    def __init__(self, base_dir: str | None = None) -> None:
        # Default to repo-level blueprints directory
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.getcwd(), "blueprints"))
        self._manifests: Dict[str, BlueprintManifest] = {}

    def load(self) -> None:
        if not os.path.isdir(self.base_dir):
            raise RuntimeError(f"Blueprints directory not found: {self.base_dir}")
        manifests: Dict[str, BlueprintManifest] = {}
        for fname in sorted(os.listdir(self.base_dir)):
            if not fname.endswith(".json"):
                continue
            if fname == "report.json":
                continue
            path = os.path.join(self.base_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = BlueprintManifest(**data)
            except Exception as e:
                raise RuntimeError(f"Invalid blueprint manifest {fname}: {e}") from e
            if manifest.id in manifests:
                raise RuntimeError(f"Duplicate blueprint id: {manifest.id}")
            manifests[manifest.id] = manifest
        # If all valid, install atomically
        self._manifests = manifests

    def list(self) -> List[BlueprintSummary]:
        return [summarize(m) for m in self._manifests.values()]

    def get(self, blueprint_id: str) -> BlueprintManifest:
        m = self._manifests.get(blueprint_id)
        if not m:
            raise KeyError(blueprint_id)
        return m


# Singleton for app use
_REGISTRY: BlueprintRegistry | None = None


def registry() -> BlueprintRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = BlueprintRegistry()
        _REGISTRY.load()
    return _REGISTRY


