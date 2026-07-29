"""Integration tests for Vestiaire supplier profit pipeline boundary."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.models import BuyDecision
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate
from supplier.vestiaire.client import VestiaireClient


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


def _yahoo_only_aggregator() -> DomesticMarketAggregator:
    return DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
            ),
        ],
    )


def test_vestiaire_product_flows_through_full_profit_pipeline() -> None:
    client = VestiaireClient()
    connector = SupplierMarketConnector(market_aggregator=_yahoo_only_aggregator())
    supplier_product = client.search_products("Chanel wallet", max_results=1)[0]

    evaluation = connector.evaluate_product(supplier_product)
    assert evaluation.domestic_market_price is not None
    assert evaluation.domestic_market_price.average_price_jpy == 160000.0

    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate, exchange_rate=150.0)
    calculator = ProfitCalculator()
    price_result = calculator.calculate(
        product,
        Decimal(str(int(evaluation.domestic_market_price.average_price_jpy))),
        domestic_market="yahoo_auction",
    )

    assert price_result.calculation_status == "success"
    assert price_result.profit_jpy > 0
    assert price_result.profit_margin is not None
    assert price_result.roi is not None

    price_result.metadata.update(
        {
            "brand": supplier_product.brand.lower(),
            "identity_confidence_score": 0.85,
            "listing_count": 2,
            "market_signal_confidence_score": evaluation.confidence_score,
        }
    )

    discovery = DiscoveryEngine().score(price_result)
    decision = BuyDecisionEngine().decide(price_result, discovery)

    assert discovery.overall_score >= 0
    assert decision.expected_profit_jpy == price_result.profit_jpy
    assert decision.decision in {BuyDecision.BUY, BuyDecision.HOLD, BuyDecision.PASS}


def test_vestiaire_profit_matches_fashionphile_equivalent_product() -> None:
    fashionphile_product = FashionphileClient().search_products("Chanel wallet", max_results=1)[0]
    vestiaire_product = VestiaireClient().search_products("Chanel wallet", max_results=1)[0]
    connector = SupplierMarketConnector(market_aggregator=_yahoo_only_aggregator())

    fashionphile_evaluation = connector.evaluate_product(fashionphile_product)
    vestiaire_evaluation = connector.evaluate_product(vestiaire_product)
    calculator = ProfitCalculator()

    fashionphile_result = calculator.calculate(
        _candidate_to_product(to_product_candidate(fashionphile_product)),
        Decimal(str(int(fashionphile_evaluation.domestic_market_price.average_price_jpy))),  # type: ignore[union-attr]
        domestic_market="yahoo_auction",
    )
    vestiaire_result = calculator.calculate(
        _candidate_to_product(to_product_candidate(vestiaire_product)),
        Decimal(str(int(vestiaire_evaluation.domestic_market_price.average_price_jpy))),  # type: ignore[union-attr]
        domestic_market="yahoo_auction",
    )

    assert fashionphile_result.profit_jpy == vestiaire_result.profit_jpy
    assert fashionphile_result.profit_margin == vestiaire_result.profit_margin
    assert fashionphile_result.roi == vestiaire_result.roi
