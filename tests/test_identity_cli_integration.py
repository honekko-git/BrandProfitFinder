"""Integration tests for identity-aware discovery CLI pipeline."""

from __future__ import annotations

import io

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from product_identity.duplicate_resolver import DuplicateResolver
from product_identity.identity_resolver import ProductIdentityResolver
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_production_discovery_pipeline,
    run_discovery_command,
)
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


def test_identity_cli_pipeline_runs_identity_duplicate_and_ranking() -> None:
    runner = _runner()
    discovery_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )

    identity_resolver = ProductIdentityResolver()
    duplicate_resolver = DuplicateResolver()
    ranked = build_production_discovery_pipeline(
        discovery_result,
        identity_resolver=identity_resolver,
        duplicate_resolver=duplicate_resolver,
    )

    assert ranked
    assert all(item.recommendation_rank is not None for item in ranked)
    assert all(item.score.total_score >= 0.0 for item in ranked)


def test_discovery_cli_output_includes_demand_opportunity_ranking() -> None:
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=_runner(),
        output=output,
    )

    rendered = output.getvalue()
    assert result.ranked_demand_opportunities
    assert "Demand Opportunity Ranking" in rendered
    assert "Product:" in rendered
    assert "Supplier:" in rendered
    assert "Demand:" in rendered
    assert "Score:" in rendered
    assert "Decision:" in rendered

    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert successful
    assert len(result.ranked_demand_opportunities) <= len(successful)
