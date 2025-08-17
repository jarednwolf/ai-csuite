from __future__ import annotations

import os, json, time, uuid
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception:  # yaml is optional; tests use example only
    yaml = None

from .interfaces import (
    AdsProvider, LifecycleProvider, ExperimentsProvider, CDPProvider, VectorStore, LLMGateway,
    LLMObservabilityProvider, RetryableError, NonRetryableError,
)


_ADAPTERS: Dict[str, Any] = {}


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Fallback minimal parser for simple key: value mappings used in example
    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not raw.startswith(" ") and line.endswith(":"):
            current_key = line[:-1]
            data[current_key] = {}
            continue
        if raw.startswith("  ") and ":" in line and current_key:
            k, v = line.split(":", 1)
            data[current_key][k.strip()] = v.strip()
    return data


def _providers_config_path() -> str:
    p = os.getenv("PROVIDERS_CONFIG_PATH") or "providers/providers.yaml"
    if os.path.exists(p):
        return p
    # fallback to example for tests
    here = os.path.dirname(os.path.dirname(__file__))
    example = os.path.join(here, "config", "providers.example.yaml")
    return example


def _models_policy_path() -> str:
    p = os.getenv("MODELS_POLICY_PATH") or "models/policy.json"
    if os.path.exists(p):
        return p
    here = os.path.dirname(os.path.dirname(__file__))
    example = os.path.join(here, "config", "models.policy.example.json")
    return example


class ProviderRegistry:
    """Simple in-process DI registry with runtime overrides and hot-reload."""

    def __init__(self) -> None:
        self._config_path = _providers_config_path()
        self._active: Dict[str, str] = {}
        self._instances: Dict[Tuple[str, str], Any] = {}
        self._overrides: Dict[str, str] = {}
        self.reload()

    def reload(self) -> Dict[str, Any]:
        cfg = _load_yaml(self._config_path) if self._config_path.endswith(('.yaml', '.yml')) else {}
        mapping = dict(cfg.get("capabilities", {}))
        # apply overrides
        for cap, name in self._overrides.items():
            mapping[cap] = name
        # freeze
        self._active = mapping
        # purge instances not used anymore
        keys = set((cap, name) for cap, name in self._active.items())
        self._instances = {k: v for k, v in self._instances.items() if k in keys}
        return {"active": dict(self._active)}

    # ----- Factories -----
    def _build(self, capability: str, name: str) -> Any:
        key = (capability, name)
        if key in self._instances:
            return self._instances[key]
        # lazy import to keep startup fast and offline
        from .adapters import (
            mock_ads, noop_ads, mock_lifecycle, mock_experiments, mock_cdp, mock_vectorstore,
            mock_llm_gateway, litellm_gateway, openrouter_gateway, mock_llm_observability,
            mock_vectorstore_a, mock_vectorstore_b,
        )
        factory_map: Dict[str, Any] = {
            "mock_ads": mock_ads.Adapter,
            "noop_ads": noop_ads.Adapter,
            "mock_lifecycle": mock_lifecycle.Adapter,
            "mock_experiments": mock_experiments.Adapter,
            "mock_cdp": mock_cdp.Adapter,
            "mock_vectorstore": mock_vectorstore.Adapter,
            "mock_vectorstore_a": mock_vectorstore_a.Adapter,
            "mock_vectorstore_b": mock_vectorstore_b.Adapter,
            "mock_llm_gateway": mock_llm_gateway.Adapter,
            "litellm_gateway": litellm_gateway.Adapter,
            "openrouter_gateway": openrouter_gateway.Adapter,
            "mock_llm_observability": mock_llm_observability.Adapter,
        }
        if name not in factory_map:
            raise NonRetryableError(f"unknown adapter '{name}' for capability '{capability}'")
        inst = factory_map[name](config={"policy_path": _models_policy_path()})
        self._instances[key] = inst
        return inst

    # ----- Accessors -----
    def get(self, capability: str) -> Any:
        name = self._active.get(capability)
        if not name:
            raise NonRetryableError(f"no adapter configured for capability '{capability}'")
        return self._build(capability, name)

    def set_override(self, capability: str, adapter_name: str) -> None:
        self._overrides[capability] = adapter_name
        self.reload()

    def list_active(self) -> Sequence[Mapping[str, Any]]:
        out = []
        for cap in sorted(self._active.keys()):
            name = self._active[cap]
            try:
                inst = self._build(cap, name)
                health = getattr(inst, "health", lambda: {"ok": True})
                h = health()
                ok = bool(h.get("ok", True)) if isinstance(h, dict) else True
            except Exception:
                ok = False
            out.append({"capability": cap, "adapter": name, "healthy": ok})
        return out

    # ----- Conformance runner (minimal offline) -----
    def run_conformance(self, capabilities: Sequence[str] | None = None, adapters: Sequence[str] | None = None) -> Mapping[str, Any]:
        caps = list(capabilities or sorted(set(self._active.keys())))
        summary = {"total": 0, "passed": 0, "failed": 0}
        reports = []
        for cap in caps:
            name = self._active.get(cap)
            if not name:
                continue
            if adapters and name not in adapters:
                continue
            start = time.time()
            ok = True
            errors: Sequence[str] = []
            metrics: Dict[str, Any] = {}
            try:
                inst = self._build(cap, name)
                # Exercise minimal ops deterministically
                if cap == "ads":
                    plan = {"budget_cents": 1000, "geo": "US"}
                    r = inst.create_campaign(plan)
                    _ = inst.report({"campaign_id": r.get("id")})
                    inst.pause(r.get("id"))
                elif cap == "lifecycle":
                    _ = inst.send({"to": "user@example.com", "body": "hi"})
                    _ = inst.schedule([], {"policy": "now"})
                elif cap == "experiments":
                    inst.set_flag("feature_x", True)
                    _ = inst.get_flag("feature_x", False)
                    _ = inst.ramp("cap.ads", 5)
                elif cap == "cdp":
                    inst.upsert_profile({"user_id": "u1", "traits": {"tier": "gold"}})
                    inst.ingest_event({"user_id": "u1", "event": "login"})
                    _ = inst.get_profile("u1")
                elif cap == "vectorstore":
                    inst.index([{"id": "d1", "text": "hello world"}])
                    _ = inst.search("hello", 5)
                    _ = inst.swap("index-v2")
                elif cap == "llm_gateway":
                    _ = inst.models()
                    _ = inst.route("hello", ["test"]) 
                else:
                    # Unknown capability is considered non-fatal for now
                    pass
                metrics = {"latency_ms": int((time.time() - start) * 1000), "attempts": 1}
            except RetryableError as e:
                ok = False
                errors = [f"RetryableError:{str(e)}"]
            except NonRetryableError as e:
                ok = False
                errors = [f"NonRetryableError:{str(e)}"]
            except Exception as e:
                ok = False
                errors = [f"Unexpected:{str(e)}"]
            reports.append({
                "capability": cap,
                "adapter": name,
                "pass": ok,
                "metrics": metrics,
                "errors": list(errors),
            })
            summary["total"] += 1
            summary["passed" if ok else "failed"] += 1
        # stable ordering
        reports.sort(key=lambda r: (str(r.get("capability")), str(r.get("adapter"))))
        return {"summary": summary, "reports": reports}


_global_registry: Optional[ProviderRegistry] = None


def registry() -> ProviderRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
    return _global_registry


