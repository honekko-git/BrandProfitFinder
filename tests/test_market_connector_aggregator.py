"""Tests for SupplierMarketConnector domestic market aggregator integration."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    FakeMercariDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.market_connector import SupplierMarketConnector
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType, to_product_candidate


def _sample_supplier_product() -> SupplierProduct:
    return SupplierProduct(
        supplier_name="fashionphile",
        external_id="fp-chanel-wallet-001",
        title="Classic Wallet",
        brand="CHANEL",
        category="wallets",
        condition=SupplierType.USED.value,
        purchase_price=700.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-chanel-wallet-001",
        image_urls=[],
        availability="in_stock",
    )


def _yahoo_only_aggregator(
    client: FakeYahooAuctionClient | None = None,
) -> DomesticMarketAggregator:
    return DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(client or FakeYahooAuctionClient()),
            ),
        ],
    )


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


def _profit_for_evaluation(
    supplier_product: SupplierProduct,
    evaluation,
    *,
    exchange_rate: float = 150.0,
):
    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate, exchange_rate=exchange_rate)
    calculator = ProfitCalculator()
    assert evaluation.domestic_market_price is not None
    return calculator.calculate(
        product,
        Decimal(str(int(evaluation.domestic_market_price.average_price_jpy))),
        domestic_market="yahoo_auction",
    )


def test_yahoo_only_aggregator_path_succeeds() -> None:
    connector = SupplierMarketConnector(market_aggregator=_yahoo_only_aggregator())
    fashionphile = FashionphileClient()
    supplier_product = fashionphile.search_products("Chanel wallet", max_results=1)[0]

    evaluation = connector.evaluate_product(supplier_product)

    assert evaluation.domestic_market_price is not None
    assert evaluation.domestic_market_price.average_price_jpy == 160000.0
    assert evaluation.domestic_market_price.median_price_jpy == 160000.0
    assert evaluation.confidence_score == 0.6
    assert evaluation.metadata["source"] == "domestic_market_aggregator"
    assert evaluation.metadata["sources"] == ["yahoo_auction"]


def test_legacy_yahoo_path_matches_yahoo_only_aggregator_path() -> None:
    fashionphile = FashionphileClient()
    supplier_product = fashionphile.search_products("Chanel wallet", max_results=1)[0]
    yahoo_client = FakeYahooAuctionClient()

    legacy_connector = SupplierMarketConnector(market_client=yahoo_client)
    aggregator_connector = SupplierMarketConnector(
        market_aggregator=_yahoo_only_aggregator(yahoo_client),
    )

    legacy_evaluation = legacy_connector.evaluate_product(supplier_product)
    aggregator_evaluation = aggregator_connector.evaluate_product(supplier_product)

    legacy_price = legacy_evaluation.domestic_market_price
    aggregator_price = aggregator_evaluation.domestic_market_price
    assert legacy_price is not None
    assert aggregator_price is not None

    assert legacy_price.product_keyword == aggregator_price.product_keyword
    assert legacy_price.average_price_jpy == aggregator_price.average_price_jpy
    assert legacy_price.median_price_jpy == aggregator_price.median_price_jpy
    assert legacy_price.min_price_jpy == aggregator_price.min_price_jpy
    assert legacy_price.max_price_jpy == aggregator_price.max_price_jpy
    assert legacy_price.sample_count == aggregator_price.sample_count
    assert legacy_price.confidence_score == aggregator_price.confidence_score

    legacy_profit = _profit_for_evaluation(supplier_product, legacy_evaluation)
    aggregator_profit = _profit_for_evaluation(supplier_product, aggregator_evaluation)

    assert legacy_profit.profit_jpy == aggregator_profit.profit_jpy
    assert legacy_profit.profit_margin == aggregator_profit.profit_margin
    assert legacy_profit.roi == aggregator_profit.roi


def test_yahoo_and_mercari_fake_merge_reflected_in_evaluation() -> None:
    fashionphile = FashionphileClient()
    supplier_product = fashionphile.search_products("Chanel wallet", max_results=1)[0]
    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
            ),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient([130000, 170000]),
            ),
        ],
    )
    yahoo_only = SupplierMarketConnector(market_aggregator=_yahoo_only_aggregator())
    multi_market = SupplierMarketConnector(market_aggregator=aggregator)

    yahoo_evaluation = yahoo_only.evaluate_product(supplier_product)
    multi_evaluation = multi_market.evaluate_product(supplier_product)

    assert yahoo_evaluation.domestic_market_price is not None
    assert multi_evaluation.domestic_market_price is not None
    assert multi_evaluation.metadata["sources"] == ["yahoo_auction", "mercari"]
    assert multi_evaluation.domestic_market_price.sample_count == 7
    assert (
        multi_evaluation.domestic_market_price.average_price_jpy
        != yahoo_evaluation.domestic_market_price.average_price_jpy
    )
    assert multi_evaluation.domestic_market_price.average_price_jpy < 160000.0


def test_aggregator_continues_when_one_market_client_fails() -> None:
    fashionphile = FashionphileClient()
    supplier_product = fashionphile.search_products("Chanel wallet", max_results=1)[0]
    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
            ),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(should_fail=True),
            ),
        ],
    )
    connector = SupplierMarketConnector(market_aggregator=aggregator)

    evaluation = connector.evaluate_product(supplier_product)

    assert evaluation.domestic_market_price is not None
    assert evaluation.domestic_market_price.average_price_jpy == 160000.0
    assert evaluation.metadata["sources"] == ["yahoo_auction"]
    assert "errors" in evaluation.metadata


def test_empty_market_returns_safe_result_without_exception() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient([]),
            ),
        ],
    )
    connector = SupplierMarketConnector(market_aggregator=aggregator)

    evaluation = connector.evaluate_product(_sample_supplier_product())

    assert evaluation.domestic_market_price is None
    assert evaluation.confidence_score == 0.0
    assert evaluation.metadata["sample_count"] == 0
    assert evaluation.metadata["sources"] == []
