"""Pipeline tests for domestic market aggregation."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.adapter import calculate_market_price
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.market_connector.query_builder import build_market_query
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


def test_domestic_market_aggregator_preserves_profit_calculation() -> None:
    supplier_product = FashionphileClient().search_products("Chanel wallet", max_results=1)[0]
    query = build_market_query(supplier_product)
    yahoo_client = FakeYahooAuctionClient()

    direct_listings = yahoo_client.search_sold_items(query, max_results=20)
    direct_market_price = calculate_market_price(direct_listings, product_keyword=query)

    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(yahoo_client),
            ),
        ]
    )
    aggregate_result = aggregator.aggregate(query, max_results=20)

    assert aggregate_result.average_price_jpy == direct_market_price.average_price_jpy
    assert aggregate_result.median_price_jpy == direct_market_price.median_price_jpy
    assert aggregate_result.confidence_score == direct_market_price.confidence_score

    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate, exchange_rate=150.0)
    calculator = ProfitCalculator()

    direct_profit = calculator.calculate(
        product,
        Decimal(str(int(direct_market_price.average_price_jpy))),
        domestic_market="yahoo_auction",
    )
    aggregate_profit = calculator.calculate(
        product,
        Decimal(str(int(aggregate_result.average_price_jpy))),
        domestic_market="yahoo_auction",
    )

    assert direct_profit.calculation_status == "success"
    assert aggregate_profit.calculation_status == "success"
    assert direct_profit.profit_jpy == aggregate_profit.profit_jpy
    assert direct_profit.profit_margin == aggregate_profit.profit_margin
    assert direct_profit.roi == aggregate_profit.roi
