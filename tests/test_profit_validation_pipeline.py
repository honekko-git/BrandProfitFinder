"""Pipeline tests for profit validation discovery."""

from __future__ import annotations

from decimal import Decimal

from app.validation_pipeline import run_profit_validation_search
from profit_discovery.cli.discovery_command import build_default_discovery_runner
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.discovery_validation.ranking import create_validation_ranking
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner


def test_profit_validation_pipeline_maps_purchase_domestic_and_decision() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    result = run_profit_validation_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )

    assert result.validation_count >= 1
    item = result.snapshot.validation_ranking[0]
    candidate = result.snapshot.candidates_by_id[item.external_id]

    assert item.purchase_source
    assert item.purchase_price > 0
    assert item.domestic_market
    assert item.domestic_price > 0
    assert item.estimated_profit is not None
    assert item.profit_margin is not None
    assert item.validation_score > 0
    assert item.decision in {BuyDecision.BUY.value, BuyDecision.HOLD.value, BuyDecision.PASS.value}
    assert candidate.profit_result is not None
    assert item.estimated_profit == candidate.profit_result.profit_jpy


def test_create_validation_ranking_preserves_profit_integrity() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    discovery_result = MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )
    candidate = next(
        item for item in discovery_result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )
    dashboard_result = run_profit_validation_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )
    validation_item = dashboard_result.snapshot.validation_ranking[0]

    assert candidate.profit_result is not None
    assert validation_item.estimated_profit == candidate.profit_result.profit_jpy
    assert float(validation_item.profit_margin) == float(candidate.profit_result.profit_margin)
    assert validation_item.purchase_price == Decimal(str(int(candidate.profit_result.purchase_price_jpy)))
