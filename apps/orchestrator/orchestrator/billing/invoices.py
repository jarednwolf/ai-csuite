from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy.orm import Session

from ..models import BillingInvoice


def generate_mock_invoice(db: Session, tenant_id: str, period: str, meters: Dict[str, int], plan: str) -> Dict:
    # Deterministic price card
    prices = {
        "community": {"tokens": 0.0, "runs": 0.0, "preview_minutes": 0.0, "storage_mb": 0.0, "api_calls": 0.0},
        "hosted": {"tokens": 0.000002, "runs": 0.05, "preview_minutes": 0.01, "storage_mb": 0.002, "api_calls": 0.0005},
        "enterprise": {"tokens": 0.000001, "runs": 0.02, "preview_minutes": 0.005, "storage_mb": 0.001, "api_calls": 0.0002},
    }[plan]
    items = {}
    total_usd = 0.0
    for k, v in meters.items():
        price = float(prices.get(k, 0.0))
        cost = float(v or 0) * price
        items[k] = {"qty": int(v or 0), "unit_price": price, "cost": round(cost, 4)}
        total_usd += cost
    amount_cents = int(round(total_usd * 100.0))
    row = BillingInvoice(id=str(uuid.uuid4()), tenant_id=tenant_id, period=period, amount_cents=amount_cents, line_items=items, status="mock")
    db.add(row)
    db.commit()
    return {"invoice_id": row.id, "tenant_id": tenant_id, "period": period, "amount_cents": amount_cents, "line_items": items, "status": row.status}


