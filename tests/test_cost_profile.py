"""Tests for batch cost profiles."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from profit_discovery.discovery_validation.batch_profit.costs import (
    CostProfile,
    CostProfileStore,
    compute_estimated_costs,
    default_cost_profiles,
)


def _price_result(profit: Decimal = Decimal("10000")) -> PriceResult:
    return PriceResult(
        source_currency="USD",
        source_original_price=Decimal("695"),
        purchase_price_jpy=Decimal("111200"),
        domestic_sale_price_jpy=Decimal("160000"),
        profit_jpy=profit,
        profit_margin=Decimal("0.05"),
        roi=Decimal("0.05"),
        calculation_status="success",
    )


def test_standard_profile_is_incomplete() -> None:
    profile = default_cost_profiles()["standard"]
    assert not profile.is_net_complete()
    net, costs = compute_estimated_costs(
        profile=profile,
        purchase_price_jpy=Decimal("111200"),
        selling_price_jpy=Decimal("160000"),
        gross_profit_result=_price_result(),
    )
    assert net is None
    assert costs.unconfigured_fields


def test_conservative_profile_can_compute_net() -> None:
    profile = default_cost_profiles()["conservative"]
    assert profile.is_net_complete()
    net, costs = compute_estimated_costs(
        profile=profile,
        purchase_price_jpy=Decimal("111200"),
        selling_price_jpy=Decimal("160000"),
        gross_profit_result=_price_result(Decimal("20000")),
    )
    assert net is not None
    assert costs.total_additional_costs_jpy > 0


def test_custom_profile_persistence(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    store = CostProfileStore(profiles=default_cost_profiles(), storage_path=path)
    custom = CostProfile(profile_name="Custom", international_shipping_jpy=Decimal("3000"))
    store.save_profile(custom)
    reloaded = CostProfileStore(storage_path=path)
    assert reloaded.get("custom").international_shipping_jpy == Decimal("3000")
