"""Tests for supplier to domestic market connector foundation."""

from __future__ import annotations

from decimal import Decimal

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from marketplace.yahoo_auction.models import YahooAuctionListing
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.market_connector import (
    SupplierMarketConnector,
    build_market_query,
)
from profit_discovery.models import BuyDecision
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType, to_product_candidate


class _RecordingMarketClient:
    def __init__(self, listings: list[YahooAuctionListing] | None = None) -> None:
        self.listings = listings or []
        self.last_keyword: str = ""
        self.last_max_results: int = 0
        self.call_count = 0

    def search_sold_items(
        self,
        keyword: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[YahooAuctionListing]:
        self.call_count += 1
        self.last_keyword = keyword
        self.last_max_results = max_results
        _ = page
        return self.listings


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


def test_build_market_query_uses_brand_and_title_only() -> None:
    query = build_market_query(_sample_supplier_product())

    assert query == "CHANEL Classic Wallet"
    assert "fashionphile" not in query.lower()
    assert "700" not in query
    assert "USD" not in query


def test_supplier_product_reaches_yahoo_auction_client() -> None:
    market_client = _RecordingMarketClient(
        listings=[
            YahooAuctionListing(
                listing_id="ya-test-1",
                title="Chanel Wallet",
                brand="Chanel",
                price_jpy=160000,
            )
        ]
    )
    connector = SupplierMarketConnector(market_client=market_client)

    connector.evaluate_product(_sample_supplier_product())

    assert market_client.call_count == 1
    assert "CHANEL" in market_client.last_keyword
    assert "Wallet" in market_client.last_keyword


def test_connector_generates_domestic_market_price() -> None:
    connector = SupplierMarketConnector(market_client=FakeYahooAuctionClient())

    fashionphile = FashionphileClient()
    supplier_product = fashionphile.search_products("Chanel wallet", max_results=1)[0]
    evaluation = connector.evaluate_product(supplier_product)

    assert evaluation.domestic_market_price is not None
    assert evaluation.domestic_market_price.average_price_jpy == 160000.0
    assert evaluation.domestic_market_price.median_price_jpy == 160000.0
    assert evaluation.confidence_score == 0.6


def test_connector_returns_safe_empty_result_when_no_market_matches() -> None:
    connector = SupplierMarketConnector(market_client=_RecordingMarketClient(listings=[]))

    evaluation = connector.evaluate_product(_sample_supplier_product())

    assert evaluation.domestic_market_price is None
    assert evaluation.confidence_score == 0.0
    assert evaluation.metadata["sample_count"] == 0


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


def test_full_connector_pipeline_without_changing_business_logic() -> None:
    supplier_client = FashionphileClient()
    connector = SupplierMarketConnector(
        supplier_client=supplier_client,
        market_client=FakeYahooAuctionClient(),
    )

    supplier_product = supplier_client.search_products("Chanel wallet", max_results=1)[0]
    evaluation = connector.evaluate_product(supplier_product)
    assert evaluation.domestic_market_price is not None

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

    price_result.metadata.update(
        {
            "brand": supplier_product.brand.lower(),
            "identity_confidence_score": 0.9,
            "listing_count": 2,
            "market_signal_confidence_score": evaluation.confidence_score,
        }
    )

    discovery = DiscoveryEngine().score(price_result)
    decision = BuyDecisionEngine().decide(price_result, discovery)

    assert discovery.overall_score >= 0
    assert decision.decision in {BuyDecision.BUY, BuyDecision.HOLD, BuyDecision.PASS}
    assert decision.expected_profit_jpy == price_result.profit_jpy
