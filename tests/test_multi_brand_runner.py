"""Tests for multi-brand discovery runner."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryRunner, rank_discovery_results
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from supplier.fashionphile.client import FashionphileClient


def _runner() -> MultiBrandDiscoveryRunner:
    supplier_client = FashionphileClient()
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


def test_multi_brand_runner_processes_two_brands_successfully() -> None:
    result = _runner().run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=3,
        ),
    )

    assert result.successful_brands == ("Chanel", "Louis Vuitton")
    assert result.failed_brands == ()
    assert len(result.results) == 2
    assert all(item.metadata.get("status") == "SUCCESS" for item in result.results)


def test_multi_brand_runner_merges_candidates_from_all_brands() -> None:
    result = _runner().run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            max_results_per_brand=3,
        ),
    )

    brands = {candidate.supplier_product.brand for candidate in result.ranked_candidates}
    assert "Chanel" in brands
    assert "Louis Vuitton" in brands
    assert result.total_candidates == len(result.ranked_candidates)
    assert result.total_candidates >= 2


def test_multi_brand_runner_ranks_merged_candidates() -> None:
    result = _runner().run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            max_results_per_brand=3,
        ),
    )

    ranked_again = rank_discovery_results(list(result.ranked_candidates))
    assert [item.supplier_product.external_id for item in ranked_again] == [
        item.supplier_product.external_id for item in result.ranked_candidates
    ]

    buy_indices = [
        index
        for index, candidate in enumerate(result.ranked_candidates)
        if candidate.buy_decision is not None
        and candidate.buy_decision.decision is BuyDecision.BUY
    ]
    if len(buy_indices) >= 2:
        assert buy_indices == sorted(buy_indices)
