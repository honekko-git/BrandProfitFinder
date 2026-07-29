"""Tests that CLI demand pipeline preserves profit evaluation integrity."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_command
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRunner
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


def test_cli_profit_integrity_preserves_profit_margin_roi_and_decision() -> None:
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=_runner(),
    )

    successful_by_id = {
        candidate.supplier_product.external_id: candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    }
    assert successful_by_id

    for item in result.ranked_demand_opportunities:
        external_id = item.candidate.supplier_product.external_id
        original = successful_by_id[external_id]

        assert item.candidate.profit_result is not None
        assert original.profit_result is not None
        assert item.candidate.profit_result.profit_jpy == original.profit_result.profit_jpy
        assert item.candidate.profit_result.profit_margin == original.profit_result.profit_margin
        assert item.candidate.profit_result.roi == original.profit_result.roi
        assert item.candidate.buy_decision is not None
        assert original.buy_decision is not None
        assert item.candidate.buy_decision.decision == original.buy_decision.decision
