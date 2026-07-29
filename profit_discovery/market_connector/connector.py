"""Orchestration connector between supplier products and domestic market clients."""

from __future__ import annotations

from marketplace.domestic_market.aggregator import DomesticMarketAggregator
from marketplace.domestic_market.models import DomesticMarketAggregateResult
from marketplace.yahoo_auction.adapter import calculate_market_price
from marketplace.yahoo_auction.base import YahooAuctionClientProtocol
from marketplace.yahoo_auction.models import DomesticMarketPrice
from supplier.base import SupplierClient
from supplier.models import SupplierProduct

from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.market_connector.query_builder import build_market_query


def _aggregate_to_domestic_market_price(
    aggregate: DomesticMarketAggregateResult,
    *,
    product_keyword: str,
) -> DomesticMarketPrice:
    """Convert an aggregate result into the connector's domestic price model."""
    combined_prices = [price for snapshot in aggregate.snapshots for price in snapshot.prices]
    sample_count = int(aggregate.metadata.get("sample_count", len(combined_prices)))

    return DomesticMarketPrice(
        product_keyword=product_keyword,
        average_price_jpy=aggregate.average_price_jpy,
        median_price_jpy=aggregate.median_price_jpy,
        min_price_jpy=min(combined_prices),
        max_price_jpy=max(combined_prices),
        sample_count=sample_count,
        confidence_score=aggregate.confidence_score,
        metadata={
            "source": "domestic_market_aggregator",
            "sources": list(aggregate.sources),
            **{
                key: value
                for key, value in aggregate.metadata.items()
                if key not in {"sample_count", "errors"}
            },
        },
    )


class SupplierMarketConnector:
    """
    Connect supplier products to domestic market price intelligence.

    Orchestration only: no profit calculation, ranking, or supplier/marketplace rules.
    """

    def __init__(
        self,
        *,
        supplier_client: SupplierClient | None = None,
        market_client: YahooAuctionClientProtocol | None = None,
        market_aggregator: DomesticMarketAggregator | None = None,
        max_results: int = 20,
    ) -> None:
        if market_aggregator is None and market_client is None:
            raise ValueError("Either market_client or market_aggregator must be provided")
        self._supplier_client = supplier_client
        self._market_client = market_client
        self._market_aggregator = market_aggregator
        self._max_results = max_results

    @property
    def supplier_client(self) -> SupplierClient | None:
        return self._supplier_client

    @property
    def market_client(self) -> YahooAuctionClientProtocol | None:
        return self._market_client

    @property
    def market_aggregator(self) -> DomesticMarketAggregator | None:
        return self._market_aggregator

    def evaluate_product(self, product: SupplierProduct) -> MarketEvaluationResult:
        """Evaluate one supplier product against domestic sold market data."""
        matched_keyword = build_market_query(product)
        if self._market_aggregator is not None:
            return self._evaluate_via_aggregator(product, matched_keyword)
        return self._evaluate_via_market_client(product, matched_keyword)

    def _evaluate_via_market_client(
        self,
        product: SupplierProduct,
        matched_keyword: str,
    ) -> MarketEvaluationResult:
        listings = self._market_client.search_sold_items(  # type: ignore[union-attr]
            matched_keyword,
            max_results=self._max_results,
        )

        if not listings:
            return MarketEvaluationResult(
                supplier_product_id=product.external_id,
                domestic_market_price=None,
                matched_keyword=matched_keyword,
                confidence_score=0.0,
                metadata={
                    "sample_count": 0,
                    "source": "yahoo_auction",
                },
            )

        market_price = calculate_market_price(
            listings,
            product_keyword=matched_keyword,
        )
        return MarketEvaluationResult(
            supplier_product_id=product.external_id,
            domestic_market_price=market_price,
            matched_keyword=matched_keyword,
            confidence_score=market_price.confidence_score,
            metadata={
                "sample_count": market_price.sample_count,
                **dict(market_price.metadata),
            },
        )

    def _evaluate_via_aggregator(
        self,
        product: SupplierProduct,
        matched_keyword: str,
    ) -> MarketEvaluationResult:
        aggregate = self._market_aggregator.aggregate(  # type: ignore[union-attr]
            matched_keyword,
            max_results=self._max_results,
        )
        combined_prices = [price for snapshot in aggregate.snapshots for price in snapshot.prices]
        metadata = {
            "sample_count": int(aggregate.metadata.get("sample_count", len(combined_prices))),
            "source": "domestic_market_aggregator",
            "sources": list(aggregate.sources),
        }
        if "errors" in aggregate.metadata:
            metadata["errors"] = aggregate.metadata["errors"]

        if not combined_prices:
            return MarketEvaluationResult(
                supplier_product_id=product.external_id,
                domestic_market_price=None,
                matched_keyword=matched_keyword,
                confidence_score=0.0,
                metadata=metadata,
            )

        market_price = _aggregate_to_domestic_market_price(
            aggregate,
            product_keyword=matched_keyword,
        )
        return MarketEvaluationResult(
            supplier_product_id=product.external_id,
            domestic_market_price=market_price,
            matched_keyword=matched_keyword,
            confidence_score=market_price.confidence_score,
            metadata={
                **metadata,
                **dict(market_price.metadata),
            },
        )
