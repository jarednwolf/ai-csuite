import importlib

def test_adapter_acme_ads_import_and_health():
    m = importlib.import_module('orchestrator.providers.adapters.acme_ads')
    Adapter = getattr(m, 'Adapter')
    inst = Adapter(config={})
    h = inst.health()
    assert isinstance(h, dict) and h.get('ok') is True
