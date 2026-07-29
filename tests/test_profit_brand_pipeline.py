"""Pipeline tests for profit-demand brand and category discovery."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.brand_catalog import BrandCatalog
from profit_discovery.category_catalog import BrandCategoryResolver, CategoryCatalog
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_discovery_search_targets,
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


def test_profit_brand_pipeline_runs_through_opportunity_ranking() -> None:
    catalog = BrandCatalog.default()
    top_brands = [profile.name for profile in catalog.get_by_opportunity_score()[:2]]
    search_targets = build_discovery_search_targets(top_brands, category_priority="HIGH")
    assert search_targets is not None

    runner = _runner()
    direct_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=top_brands,
            max_results_per_brand=1,
            search_targets=search_targets[:1],
        ),
    )
    cli_result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=top_brands,
            category_priority="HIGH",
            max_results_per_brand=1,
            search_targets=search_targets[:1],
        ),
        runner=runner,
    )

    assert cli_result.ranked_opportunities
    assert len(cli_result.ranked_opportunities) == len(direct_result.ranked_opportunities)

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


def test_profit_brand_catalog_and_category_catalog_generate_wallet_query() -> None:
    brand = BrandCatalog.default().get_by_opportunity_score()[0]
    categories = CategoryCatalog.default().get_high_priority_categories()
    targets = BrandCategoryResolver().resolve([brand.name], list(categories))

    assert targets[0].query == f"{brand.name} Wallet"
