"""Pipeline tests for automatic demand linking."""

from __future__ import annotations

from pathlib import Path

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.opportunity import build_auto_demand_integrated_ranking
from profit_intelligence.demand import DemandLookup
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


def test_auto_demand_pipeline_links_discovery_to_integrated_ranking() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    lookup = DemandLookup(fixture_dir=fixture_dir)
    runner = _runner()

    discovery_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )

    ranked = build_auto_demand_integrated_ranking(
        discovery_result.ranked_candidates,
        lookup=lookup,
    )

    assert ranked
    assert ranked[0].recommendation_rank == 1
    assert ranked[0].demand_profile is not None
    assert ranked[0].demand_profile.query == "Chanel Wallet"
    assert ranked[0].score.demand_score > 0.0

    successful = [
        candidate
        for candidate in discovery_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    assert successful

    for item in ranked:
        matching = next(
            candidate
            for candidate in successful
            if candidate.supplier_product.external_id == item.candidate.supplier_product.external_id
        )
        assert item.candidate.profit_result is not None
        assert matching.profit_result is not None
        assert item.candidate.profit_result.profit_jpy == matching.profit_result.profit_jpy
        assert item.candidate.profit_result.roi == matching.profit_result.roi
        assert item.candidate.buy_decision is not None
        assert matching.buy_decision is not None
        assert item.candidate.buy_decision.decision == matching.buy_decision.decision
