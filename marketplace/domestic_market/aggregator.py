"""Domestic market aggregation across multiple price sources."""

from __future__ import annotations

from marketplace.domestic_market.adapter import merge_market_prices, snapshot_from_prices
from marketplace.domestic_market.base import DomesticMarketClient
from marketplace.domestic_market.models import (
    DomesticMarketAggregateResult,
    DomesticMarketSource,
)


class DomesticMarketAggregator:
    """Aggregate sold prices from multiple domestic market clients."""

    def __init__(
        self,
        clients: list[tuple[DomesticMarketSource, DomesticMarketClient]],
    ) -> None:
        self._clients = tuple(clients)

    @property
    def clients(self) -> tuple[tuple[DomesticMarketSource, DomesticMarketClient], ...]:
        """Return configured domestic market client sources."""
        return self._clients

    def aggregate(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> DomesticMarketAggregateResult:
        """Query all enabled domestic markets and merge sold prices."""
        snapshots = []
        errors: list[str] = []

        for source, client in self._clients:
            if not source.enabled:
                continue
            try:
                prices = client.search_sold_items(
                    query,
                    page=page,
                    max_results=max_results,
                )
                snapshot = snapshot_from_prices(
                    source.name,
                    prices,
                    metadata={"market_name": client.market_name},
                )
                if snapshot is not None:
                    snapshots.append(snapshot)
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

        result = merge_market_prices(snapshots)
        if errors:
            return DomesticMarketAggregateResult(
                average_price_jpy=result.average_price_jpy,
                median_price_jpy=result.median_price_jpy,
                confidence_score=result.confidence_score,
                sources=result.sources,
                snapshots=result.snapshots,
                metadata={**result.metadata, "errors": errors},
            )
        return result
