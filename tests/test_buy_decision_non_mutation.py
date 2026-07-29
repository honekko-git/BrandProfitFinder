"""Non-mutation tests for buy decision layer."""

from __future__ import annotations

import copy
from decimal import Decimal

from models.price_result import PriceResult
from profit_discovery.buy_decision_engine import BuyDecisionEngine, attach_buy_decision_metadata
from profit_intelligence.discovery_engine import DiscoveryEngine
from profit_intelligence.discovery_models import DiscoveryScore


def _profit_fields(result: PriceResult) -> dict[str, object]:
    return {
        "profit_jpy": result.profit_jpy,
        "profit_margin": result.profit_margin,
        "roi": result.roi,
    }


def test_buy_decision_does_not_modify_profit_fields() -> None:
    result = PriceResult(
        profit_jpy=Decimal("15000"),
        profit_margin=Decimal("28"),
        roi=Decimal("75"),
        domestic_sale_price_jpy=Decimal("100000"),
        purchase_price_jpy=Decimal("60000"),
        total_cost_jpy=Decimal("82000"),
        marketplace_fee_jpy=Decimal("3000"),
        source_currency="USD",
        exchange_rate=Decimal("150"),
        source_purchase_price=Decimal("400"),
        calculation_status="success",
        metadata={"brand": "gucci", "identity_confidence_score": 0.9, "listing_count": 2},
    )
    before = _profit_fields(result)
    snapshot = copy.deepcopy(result)
    discovery = DiscoveryEngine().score(result)

    decision = BuyDecisionEngine().decide(result, discovery)
    attach_buy_decision_metadata(result, decision)

    assert _profit_fields(result) == before
    assert result.profit_jpy == snapshot.profit_jpy
    assert result.profit_margin == snapshot.profit_margin
    assert result.roi == snapshot.roi


def test_buy_decision_does_not_modify_profit_with_explicit_discovery_score() -> None:
    result = PriceResult(
        profit_jpy=Decimal("8000"),
        profit_margin=Decimal("20"),
        roi=Decimal("40"),
        domestic_sale_price_jpy=Decimal("70000"),
        calculation_status="success",
    )
    discovery = DiscoveryScore(
        profit_score=70.0,
        demand_score=50.0,
        brand_score=50.0,
        competition_score=50.0,
        confidence_score=50.0,
        overall_score=65.0,
        warnings=("Demand data unavailable.",),
    )
    before = _profit_fields(result)

    decision = BuyDecisionEngine().decide(result, discovery)
    attach_buy_decision_metadata(result, decision)

    assert _profit_fields(result) == before
