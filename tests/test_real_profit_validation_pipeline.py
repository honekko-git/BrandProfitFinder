"""Pipeline tests for real profit verification."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market.yahoo_auction.transport import FakeYahooAuctionTransport
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.discovery_validation.real_profit_verification import build_real_profit_verifications
from profit_discovery.models import BuyDecision
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate
from tests.test_yahoo_real_pipeline import _candidate_to_product, _sample_transport


def test_real_profit_validation_pipeline_matches_existing_profit_calculation() -> None:
    transport = _sample_transport()
    results = build_real_profit_verifications(
        brand="Chanel",
        category="Wallet",
        yahoo_transport=transport,
    )

    assert results
    item = results[0]
    assert item.purchase_source == "Fashionphile"
    assert item.domestic_source == "Yahoo Auction"
    assert item.domestic_sold_samples == 5
    assert item.estimated_profit is not None
    assert item.profit_margin is not None
    assert item.roi is not None
    assert item.decision in {BuyDecision.BUY.value, BuyDecision.HOLD.value, BuyDecision.PASS.value}

    supplier_product = FashionphileClient().search_products("Chanel wallet", max_results=1)[0]
    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate, exchange_rate=160.0)
    baseline = ProfitCalculator().calculate(
        product,
        Decimal(str(int(item.domestic_average_jpy))),
        domestic_market="yahoo_auction",
    )

    assert item.estimated_profit == baseline.profit_jpy
    assert item.profit_margin == baseline.profit_margin
    assert item.roi == baseline.roi


def test_real_profit_validation_pipeline_supports_manual_import_fallback() -> None:
    results = build_real_profit_verifications(
        brand="Chanel",
        category="Wallet",
        yahoo_transport=FakeYahooAuctionTransport(
            default_items=[{"title": "Chanel Wallet", "sold_price": 155000, "url": "https://example.invalid/y"}]
        ),
        manual_listing=None,
    )
    assert results
    assert results[0].actual_purchase_source in {"FIXTURE", "LIVE", "IMPORT", "MIXED"}
