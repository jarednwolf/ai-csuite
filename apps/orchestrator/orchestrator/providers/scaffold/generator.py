from __future__ import annotations

import os
import json
from typing import Any, Dict, Tuple


TEMPLATE_HEADER = """
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..interfaces import RetryableError, NonRetryableError


class Adapter:
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config = dict(config or {})
        self._state = {"calls": 0}

    def health(self) -> Mapping[str, Any]:
        return {"ok": True, "calls": int(self._state.get("calls", 0))}
""".lstrip()


CAPABILITY_METHODS = {
    "ads": """
    def create_campaign(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return {"id": "camp_1", "status": "active", "plan": dict(plan or {})}

    def report(self, query: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return [{"campaign_id": str(query.get("campaign_id") or "camp_1"), "spend_cents": 0, "impressions": 0}]

    def pause(self, campaign_id: str) -> None:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return None
""",
    "lifecycle": """
    def send(self, message: Mapping[str, Any]) -> Mapping[str, Any]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return {"id": "msg_1", "status": "queued"}

    def schedule(self, batch: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]) -> Mapping[str, Any]:
        self._state["calls"] = int(self._state.get("calls", 0)) + 1
        return {"status": "ok", "size": len(list(batch or []))}
""",
    "experiments": """
    def set_flag(self, key: str, value: Any) -> None:
        self._state[key] = bool(value)

    def get_flag(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def ramp(self, key: str, stage: int) -> Mapping[str, Any]:
        self._state[f"ramp:{key}"] = int(stage)
        return {"key": key, "stage": int(stage)}
""",
    "cdp": """
    def upsert_profile(self, profile: Mapping[str, Any]) -> None:
        self._state["last_profile_id"] = str((profile or {}).get("user_id") or "u1")

    def ingest_event(self, event: Mapping[str, Any]) -> None:
        self._state["last_event"] = dict(event or {})

    def sync_audience(self, audience: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "mocked"}

    def get_profile(self, user_id: str) -> Mapping[str, Any] | None:
        if str(user_id) == str(self._state.get("last_profile_id")):
            return {"user_id": user_id, "traits": {"tier": "gold"}}
        return None
""",
    "vectorstore": """
    def index(self, docs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        self._state["docs_indexed"] = len(list(docs or []))
        return {"status": "ok", "indexed": int(self._state["docs_indexed"])}

    def search(self, query: str, k: int = 5) -> Sequence[Mapping[str, Any]]:
        return [{"id": "d1", "score": 1.0}]

    def swap(self, target: str) -> Mapping[str, Any]:
        self._state["active_index"] = str(target)
        return {"status": "ok", "active": str(target)}
""",
    "llm_gateway": """
    def models(self) -> Sequence[Mapping[str, Any]]:
        return [{"id": "mock/model", "quality": 1.0}]

    def route(self, prompt: str, tags: Sequence[str]) -> Mapping[str, Any]:
        return {"model": "mock/model", "latency_ms": 10, "output": prompt}
""",
    "llm_observability": """
    def trace_start(self, run_id: str, meta: Mapping[str, Any]) -> str:
        return "trace_1"

    def trace_stop(self, trace_id: str, meta: Mapping[str, Any]) -> None:
        return None

    def log_eval(self, name: str, score: float, meta: Mapping[str, Any]) -> None:
        return None
""",
}


def _write_text_if_changed(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        cur = None
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
    except Exception:
        cur = None
    if cur != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def generate_adapter_skeleton(*, capability: str, vendor: str, config: Dict[str, Any] | None = None) -> Dict[str, str]:
    capability = str(capability)
    vendor = str(vendor)
    # Map observability → llm_observability for canonical directory/interface
    if capability == "observability":
        capability = "llm_observability"
    adapter_mod_name = vendor
    adapter_dir = os.path.join(
        "apps", "orchestrator", "orchestrator", "providers", "adapters"
    )
    adapter_path = os.path.join(adapter_dir, f"{adapter_mod_name}.py")

    header = TEMPLATE_HEADER
    body = CAPABILITY_METHODS.get(capability, "")
    content = header + body
    _write_text_if_changed(adapter_path, content)

    # Create a minimal unit test skeleton under tests/ (vendor-specific)
    test_dir = os.path.join("apps", "orchestrator", "tests")
    test_path = os.path.join(test_dir, f"test_adapter_{adapter_mod_name}.py")
    test_code = (
        "import importlib\n"
        "\n"
        f"def test_adapter_{adapter_mod_name}_import_and_health():\n"
        f"    m = importlib.import_module('orchestrator.providers.adapters.{adapter_mod_name}')\n"
        f"    Adapter = getattr(m, 'Adapter')\n"
        f"    inst = Adapter(config={{}})\n"
        f"    h = inst.health()\n"
        f"    assert isinstance(h, dict) and h.get('ok') is True\n"
    )
    _write_text_if_changed(test_path, test_code)

    return {"adapter_path": adapter_path, "unit_test_path": test_path}


def ensure_providers_yaml_registration(*, vendor: str, capability: str, activate: bool) -> Tuple[str, bool]:
    # Ensure providers/providers.yaml exists with minimal structure
    cfg_path = os.getenv("PROVIDERS_CONFIG_PATH") or "providers/providers.yaml"
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    if not os.path.exists(cfg_path):
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("adapters: {}\ncapabilities: {}\n")

    # Read existing
    def _parse_yaml_simple(text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {"adapters": {}, "capabilities": {}}
        section = None
        for raw in text.splitlines():
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if not raw.startswith(" ") and line.endswith(":"):
                k = line[:-1]
                if k in ("adapters", "capabilities"):
                    section = k
                    if section not in data:
                        data[section] = {}
                continue
            if section in ("adapters", "capabilities") and raw.startswith("  ") and ":" in line:
                k, v = line.strip().split(":", 1)
                data[section][k.strip()] = v.strip()
        return data

    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None  # type: ignore

    txt = ""
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        txt = ""
    data = yaml.safe_load(txt) if (yaml and txt) else _parse_yaml_simple(txt)
    if not isinstance(data, dict):
        data = {"adapters": {}, "capabilities": {}}

    adapters = dict(data.get("adapters") or {})
    capabilities = dict(data.get("capabilities") or {})

    # Register adapter module name to itself (placeholder for vendor metadata)
    adapters.setdefault(vendor, vendor)
    # Do not change active capability mapping unless activate=True
    applied_activation = False
    if activate:
        capabilities[str(capability)] = vendor
        applied_activation = True

    # Serialize deterministically
    if yaml:
        out_txt = yaml.safe_dump({"adapters": adapters, "capabilities": capabilities}, sort_keys=True)
    else:
        lines = []
        lines.append("adapters:")
        for k in sorted(adapters.keys()):
            lines.append(f"  {k}: {adapters[k]}")
        lines.append("capabilities:")
        for k in sorted(capabilities.keys()):
            lines.append(f"  {k}: {capabilities[k]}")
        out_txt = "\n".join(lines) + "\n"
    _write_text_if_changed(cfg_path, out_txt)
    return cfg_path, applied_activation


def write_mock_conformance_report(*, capability: str, vendor: str, seed: int = 123) -> Dict[str, Any]:
    # Deterministic minimal report written to reports/conformance
    path = os.path.join(
        "apps", "orchestrator", "orchestrator", "reports", "conformance", f"{capability}-{vendor}.json"
    )
    report = {
        "summary": {"total": 1, "passed": 1, "failed": 0},
        "reports": [
            {
                "capability": str(capability),
                "adapter": str(vendor),
                "pass": True,
                "metrics": {"latency_ms": 1, "attempts": 1, "seed": int(seed)},
                "errors": [],
            }
        ],
        "path": path,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True)
        f.write("\n")
    return report



