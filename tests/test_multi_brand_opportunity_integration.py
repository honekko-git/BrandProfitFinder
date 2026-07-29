"""Integration tests for multi-brand runner opportunity ranking."""

from __future__ import annotations

import io

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_command
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
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


def test_multi_brand_runner_stores_ranked_opportunities() -> None:
    result = _runner().run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )

    assert result.ranked_opportunities
    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert len(result.ranked_opportunities) == len(successful)


def test_multi_brand_runner_orders_opportunities_by_score() -> None:
    result = _runner().run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )

    scores = [item.score.total_score for item in result.ranked_opportunities]
    assert scores == sorted(scores, reverse=True)
    assert all(
        item.recommendation_rank == index
        for index, item in enumerate(result.ranked_opportunities, start=1)
    )


def test_discovery_cli_displays_runner_opportunity_ranking() -> None:
    runner = _runner()
    direct_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )
    output = io.StringIO()
    cli_result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=runner,
        output=output,
    )

    assert cli_result.ranked_opportunities
    assert len(cli_result.ranked_opportunities) == len(direct_result.ranked_opportunities)
    assert [
        item.candidate.supplier_product.external_id for item in cli_result.ranked_opportunities
    ] == [
        item.candidate.supplier_product.external_id for item in direct_result.ranked_opportunities
    ]
    rendered = output.getvalue()
    top = cli_result.ranked_demand_opportunities[0]
    assert "Demand Opportunity Ranking" in rendered
    assert top.demand_profile is not None
    assert top.demand_profile.query in rendered
    assert f"{top.score.total_score:.1f}" in rendered
