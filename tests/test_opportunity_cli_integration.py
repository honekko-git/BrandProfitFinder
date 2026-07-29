"""Integration tests for opportunity ranking in discovery CLI output."""

from __future__ import annotations

import io

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_command
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRunner
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


def test_discovery_cli_output_includes_opportunity_ranking() -> None:
    output = io.StringIO()
    run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=MultiBrandDiscoveryRunner(discovery_runner=_discovery_runner()),
        output=output,
    )

    rendered = output.getvalue()
    assert "Opportunity Ranking" in rendered
    assert "Product:" in rendered
    assert "Supplier:" in rendered
    assert "Score:" in rendered
    assert "Decision:" in rendered


def test_discovery_cli_opportunity_ranking_is_sorted_by_score() -> None:
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=MultiBrandDiscoveryRunner(discovery_runner=_discovery_runner()),
    )

    ranked_opportunities = result.ranked_opportunities
    assert ranked_opportunities
    scores = [item.score.total_score for item in ranked_opportunities]
    assert scores == sorted(scores, reverse=True)
    assert all(
        item.recommendation_rank == index
        for index, item in enumerate(ranked_opportunities, start=1)
    )

    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert len(ranked_opportunities) == len(successful)
