"""Tests for showcase dashboard models."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.showcase import ShowcaseOpportunity


def test_showcase_opportunity_dataclass_fields() -> None:
    opportunity = ShowcaseOpportunity(
        rank=1,
        product_name="Chanel Wallet",
        supplier="Fashionphile",
        profit_jpy=Decimal("35000"),
        roi=Decimal("42.0"),
        demand_score=92.0,
        opportunity_score=94.5,
        decision="BUY",
        category="wallets",
        brand="Chanel",
    )

    assert opportunity.rank == 1
    assert opportunity.product_name == "Chanel Wallet"
    assert opportunity.supplier == "Fashionphile"
    assert opportunity.profit_jpy == Decimal("35000")
    assert opportunity.roi == Decimal("42.0")
    assert opportunity.demand_score == 92.0
    assert opportunity.opportunity_score == 94.5
    assert opportunity.decision == "BUY"
    assert opportunity.category == "wallets"
    assert opportunity.brand == "Chanel"
