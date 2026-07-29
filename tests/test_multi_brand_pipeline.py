"""Integration tests for multi-brand discovery pipeline."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from supplier.fashionphile.client import FashionphileClient


def _discovery_runner() -> DiscoveryRunner:
    supplier_client = FashionphileClient()
    return DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )


def test_multi_brand_pipeline_preserves_profit_metrics_for_single_brand() -> None:
    discovery_runner = _discovery_runner()
    single_brand_batch = discovery_runner.evaluate_products(
        discovery_runner.supplier_client.search_products("Chanel wallet", max_results=1),
    )
    single_candidate = next(
        result for result in single_brand_batch.results if result.status is DiscoveryCandidateStatus.SUCCESS
    )
    assert single_candidate.profit_result is not None

    multi_result = MultiBrandDiscoveryRunner(discovery_runner=discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )
    multi_candidate = next(
        candidate
        for candidate in multi_result.ranked_candidates
        if candidate.supplier_product.brand == "Chanel"
        and candidate.status is DiscoveryCandidateStatus.SUCCESS
    )
    assert multi_candidate.profit_result is not None
    assert multi_candidate.buy_decision is not None

    assert multi_candidate.profit_result.profit_jpy == single_candidate.profit_result.profit_jpy
    assert multi_candidate.profit_result.profit_margin == single_candidate.profit_result.profit_margin
    assert multi_candidate.profit_result.roi == single_candidate.profit_result.roi
    assert multi_candidate.buy_decision.decision == single_candidate.buy_decision.decision


def test_multi_brand_pipeline_runs_discovery_profit_and_buy_decision() -> None:
    discovery_runner = _discovery_runner()
    result = MultiBrandDiscoveryRunner(discovery_runner=discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )

    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
        and candidate.profit_result is not None
        and candidate.buy_decision is not None
    ]

    assert successful
    assert all(candidate.profit_result.profit_jpy > 0 for candidate in successful)
    assert all(candidate.discovery_score is not None for candidate in successful)
