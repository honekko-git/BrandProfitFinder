"""Pipeline tests for showcase dashboard integration."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import build_production_discovery_pipeline
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.showcase import ShowcaseFormatter
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


def test_showcase_pipeline_preserves_profit_roi_and_decision() -> None:
    runner = _runner()
    discovery_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )
    ranked = build_production_discovery_pipeline(discovery_result)
    showcase_items = ShowcaseFormatter().to_showcase_opportunities(ranked)

    successful_by_id = {
        candidate.supplier_product.external_id: candidate
        for candidate in discovery_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    }
    assert successful_by_id
    assert showcase_items

    for item, ranked_item in zip(showcase_items, ranked, strict=True):
        external_id = ranked_item.candidate.supplier_product.external_id
        original = successful_by_id[external_id]

        assert original.profit_result is not None
        assert item.profit_jpy == original.profit_result.profit_jpy
        assert item.roi == original.profit_result.roi
        assert original.buy_decision is not None
        assert item.decision == original.buy_decision.decision.value
