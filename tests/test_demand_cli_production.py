"""Production tests for demand-integrated discovery CLI ranking."""

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


def test_demand_cli_production_displays_demand_ranking_fields() -> None:
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=_runner(),
        output=output,
    )

    rendered = output.getvalue()
    top = result.ranked_demand_opportunities[0]

    assert "需要込み候補順位" in rendered
    assert top.demand_profile is not None
    assert top.demand_profile.query in rendered
    assert top.candidate.supplier_product.supplier_name in rendered
    assert f"{int(round(top.score.demand_score))}" in rendered
    assert f"{top.score.total_score:.1f}" in rendered
    assert top.candidate.buy_decision is not None
    assert top.candidate.buy_decision.decision.value in rendered


def test_demand_cli_production_ranking_is_sorted_by_score() -> None:
    runner = _runner()
    direct_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )
    cli_result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=runner,
    )

    ranked = cli_result.ranked_demand_opportunities
    assert ranked
    scores = [item.score.total_score for item in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(item.recommendation_rank == index for index, item in enumerate(ranked, start=1))

    successful = [
        candidate
        for candidate in direct_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert successful
    assert len(ranked) <= len(successful)
