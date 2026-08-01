"""Pipeline tests for the browser dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import run_used_luxury_dashboard_search
from app.store import DashboardResultStore
from profit_discovery.cli.discovery_command import (
    build_default_discovery_runner,
    build_production_discovery_pipeline,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner


def test_browser_pipeline_preserves_profit_integrity() -> None:
    runner = build_default_discovery_runner(used_luxury=True)

    direct_result = MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )
    direct_candidate = next(
        item for item in direct_result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )
    direct_ranked = build_production_discovery_pipeline(direct_result)

    dashboard_result = run_used_luxury_dashboard_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )

    assert dashboard_result.snapshot.arbitrage_ranking
    arbitrage = dashboard_result.snapshot.arbitrage_ranking[0]
    browser_candidate = dashboard_result.snapshot.candidates_by_id[arbitrage.external_id]

    assert direct_candidate.profit_result is not None
    assert browser_candidate.profit_result is not None
    assert browser_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert browser_candidate.profit_result.profit_margin == direct_candidate.profit_result.profit_margin
    assert browser_candidate.profit_result.roi == direct_candidate.profit_result.roi
    assert direct_candidate.buy_decision is not None
    assert browser_candidate.buy_decision is not None
    assert browser_candidate.buy_decision.decision == direct_candidate.buy_decision.decision
    assert len(direct_ranked) >= len(dashboard_result.snapshot.arbitrage_ranking)


def test_browser_search_endpoint_runs_arbitrage_ranking() -> None:
    store = DashboardResultStore()
    client = TestClient(create_app(result_store=store))
    response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )

    assert response.status_code == 200
    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking
    assert snapshot.profit_ranking
    assert snapshot.arbitrage_ranking[0].recommendation_rank == 1
