"""Tests for discovery to opportunity pipeline integration."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.opportunity import OpportunityScorer, rank_opportunities
from supplier.fashionphile.client import FashionphileClient


def test_opportunity_pipeline_preserves_discovery_outputs() -> None:
    supplier_client = FashionphileClient()
    runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    products = supplier_client.search_products("Chanel wallet", max_results=2)
    batch = runner.evaluate_products(products)

    baseline = {
        result.supplier_product.external_id: {
            "profit_jpy": result.profit_result.profit_jpy if result.profit_result else None,
            "profit_margin": result.profit_result.profit_margin if result.profit_result else None,
            "roi": result.profit_result.roi if result.profit_result else None,
            "decision": result.buy_decision.decision if result.buy_decision else None,
        }
        for result in batch.results
    }

    scorer = OpportunityScorer()
    opportunities = [
        scorer.evaluate(result)
        for result in batch.results
        if result.status is DiscoveryCandidateStatus.SUCCESS
    ]
    ranked = rank_opportunities(opportunities)

    assert len(ranked) >= 1
    assert all(item.score.total_score >= 0.0 for item in ranked)
    assert ranked[0].recommendation_rank == 1

    for item in ranked:
        external_id = item.candidate.supplier_product.external_id
        expected = baseline[external_id]
        profit_result = item.candidate.profit_result
        assert profit_result is not None
        assert profit_result.profit_jpy == expected["profit_jpy"]
        assert profit_result.profit_margin == expected["profit_margin"]
        assert profit_result.roi == expected["roi"]
        assert item.candidate.buy_decision is not None
        assert item.candidate.buy_decision.decision == expected["decision"]


def test_opportunity_pipeline_ranks_successful_candidates_by_score() -> None:
    supplier_client = FashionphileClient()
    runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    products = supplier_client.search_products("", max_results=3)
    batch = runner.evaluate_products(products)

    scorer = OpportunityScorer()
    opportunities = [
        scorer.evaluate(result)
        for result in batch.results
        if result.status is DiscoveryCandidateStatus.SUCCESS
    ]
    ranked = rank_opportunities(opportunities)

    totals = [item.score.total_score for item in ranked]
    assert totals == sorted(totals, reverse=True)
