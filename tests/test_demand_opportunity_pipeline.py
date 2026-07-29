"""Pipeline tests for demand-integrated opportunity ranking."""

from __future__ import annotations

from pathlib import Path

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.brand_catalog import BrandCatalog
from profit_discovery.category_catalog import BrandCategoryResolver, CategoryCatalog
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.opportunity import (
    analyze_demand_for_queries,
    build_demand_integrated_opportunities,
    rank_demand_integrated_opportunities,
)
from profit_intelligence.demand import DemandAnalyzer
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


def test_demand_integrated_pipeline_preserves_profit_roi_and_decision() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    analyzer = DemandAnalyzer(fixture_dir=fixture_dir)
    brand = BrandCatalog.default().get_by_opportunity_score()[0].name
    targets = BrandCategoryResolver().resolve(
        [brand],
        list(CategoryCatalog.default().get_high_priority_categories()[:1]),
    )
    assert targets
    query = targets[0].query

    demand_profiles = analyze_demand_for_queries(
        [query],
        analyzer=analyzer,
        sold_data_by_query={query: analyzer._load_fixture("chanel_wallet.json")},
    )
    assert demand_profiles

    runner = _runner()
    discovery_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=[brand],
            max_results_per_brand=1,
            search_targets=targets[:1],
        ),
    )

    successful = [
        candidate
        for candidate in discovery_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert successful

    query_by_candidate = {
        candidate.supplier_product.external_id: query for candidate in successful
    }
    opportunities = build_demand_integrated_opportunities(
        successful,
        demand_profiles_by_query={profile.query: profile for profile in demand_profiles},
        search_query_by_candidate=query_by_candidate,
    )
    ranked = rank_demand_integrated_opportunities(opportunities)

    assert ranked
    assert ranked[0].recommendation_rank == 1
    assert ranked[0].demand_profile is not None
    assert ranked[0].score.demand_score > 0.0

    baseline = {
        candidate.supplier_product.external_id: {
            "profit_jpy": candidate.profit_result.profit_jpy if candidate.profit_result else None,
            "roi": candidate.profit_result.roi if candidate.profit_result else None,
            "decision": candidate.buy_decision.decision if candidate.buy_decision else None,
        }
        for candidate in successful
    }

    for item in ranked:
        external_id = item.candidate.supplier_product.external_id
        expected = baseline[external_id]
        profit_result = item.candidate.profit_result
        assert profit_result is not None
        assert profit_result.profit_jpy == expected["profit_jpy"]
        assert profit_result.roi == expected["roi"]
        assert item.candidate.buy_decision is not None
        assert item.candidate.buy_decision.decision == expected["decision"]
