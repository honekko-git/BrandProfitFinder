"""Integration tests for supplier to Yahoo Auction domestic market profit flow."""

from __future__ import annotations

from decimal import Decimal

from marketplace.yahoo_auction.adapter import calculate_market_price
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.models import BuyDecision
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate


def _candidate_to_product(candidate: dict[str, object], *, exchange_rate: float = 150.0) -> Product:
    return Product(
        name=str(candidate["name"]),
        brand=str(candidate["brand"]),
        price=float(candidate["purchase_price"]),
        currency=str(candidate["currency"]),
        store_name=str(candidate["source"]),
        url=str(candidate.get("url") or ""),
        model=str(candidate.get("model_number") or ""),
        exchange_rate=exchange_rate,
    )


def test_supplier_to_yahoo_auction_market_price_profit_pipeline() -> None:
    supplier_client = FashionphileClient()
    market_client = FakeYahooAuctionClient()

    supplier_products = supplier_client.search_products("Chanel wallet", max_results=1)
    assert supplier_products
    supplier_product = supplier_products[0]
    assert supplier_product.purchase_price == 700.0

    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate, exchange_rate=150.0)

    sold_listings = market_client.search_sold_items("chanel wallet", max_results=20)
    market_price = calculate_market_price(sold_listings, product_keyword="chanel wallet")

    assert market_price.average_price_jpy == 160000.0
    assert market_price.sample_count == 5

    calculator = ProfitCalculator()
    price_result = calculator.calculate(
        product,
        Decimal(str(int(market_price.average_price_jpy))),
        domestic_market="yahoo_auction",
    )

    assert price_result.calculation_status == "success"
    assert price_result.profit_jpy > 0
    assert price_result.domestic_sale_price_jpy == Decimal("160000")

    price_result.metadata.update(
        {
            "brand": supplier_product.brand.lower(),
            "identity_confidence_score": 0.9,
            "listing_count": 2,
            "market_signal_confidence_score": market_price.confidence_score,
        }
    )

    discovery = DiscoveryEngine().score(price_result)
    decision = BuyDecisionEngine().decide(price_result, discovery)

    assert discovery.overall_score >= 0
    assert decision.decision in {BuyDecision.BUY, BuyDecision.HOLD, BuyDecision.PASS}
    assert decision.expected_profit_jpy == price_result.profit_jpy
