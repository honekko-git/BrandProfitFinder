"""Pipeline tests for tier-based brand catalog discovery."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.brand_catalog import BrandCatalog
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


def test_tier_catalog_runs_through_opportunity_ranking_pipeline() -> None:
    catalog = BrandCatalog.default()
    tier_s_brands = catalog.brand_names_for_tier("S")[:2]
    runner = _runner()

    direct_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=tier_s_brands,
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )
    cli_result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=tier_s_brands,
            keyword="wallet",
            max_results_per_brand=1,
        ),
        runner=runner,
    )

    assert cli_result.ranked_opportunities
    assert len(cli_result.ranked_opportunities) == len(direct_result.ranked_opportunities)
    scores = [item.score.total_score for item in cli_result.ranked_opportunities]
    assert scores == sorted(scores, reverse=True)

    baseline = {
        candidate.supplier_product.external_id: {
            "profit_jpy": candidate.profit_result.profit_jpy if candidate.profit_result else None,
            "roi": candidate.profit_result.roi if candidate.profit_result else None,
            "decision": candidate.buy_decision.decision if candidate.buy_decision else None,
        }
        for candidate in direct_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    }

    for item in cli_result.ranked_opportunities:
        external_id = item.candidate.supplier_product.external_id
        expected = baseline[external_id]
        profit_result = item.candidate.profit_result
        assert profit_result is not None
        assert profit_result.profit_jpy == expected["profit_jpy"]
        assert profit_result.roi == expected["roi"]
        assert item.candidate.buy_decision is not None
        assert item.candidate.buy_decision.decision == expected["decision"]
