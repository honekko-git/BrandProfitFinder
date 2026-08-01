"""Convert foreign prices using a frozen FX snapshot (Decimal + round_jpy)."""

from __future__ import annotations

from decimal import Decimal

from marketplace.acquisition_workspace.fx_models import FxSnapshot
from profit_policy.money import round_jpy


def convert_to_jpy(amount: Decimal, currency: str, snapshot: FxSnapshot) -> Decimal | None:
    """Convert with snapshot rate; returns whole JPY or None if rate unavailable."""
    rate = snapshot.rate_for(currency)
    if rate is None:
        return None
    if amount <= 0:
        return None
    return round_jpy(amount * rate)


def derive_exchange_rate(purchase_price: Decimal, purchase_price_jpy: Decimal) -> float | None:
    """Derive per-product rate so ProfitCalculator reconciles to imported JPY."""
    if purchase_price <= 0 or purchase_price_jpy <= 0:
        return None
    return float(purchase_price_jpy / purchase_price)
