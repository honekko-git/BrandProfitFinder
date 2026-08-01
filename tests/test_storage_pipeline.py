"""Pipeline tests for arbitrage ranking to SQLite storage."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import run_used_luxury_dashboard_search
from app.store import DashboardResultStore, SQLiteOpportunityStore
from profit_discovery.cli.discovery_command import build_default_discovery_runner
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner


def test_storage_pipeline_preserves_profit_fields(tmp_path) -> None:
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

    dashboard_result = run_used_luxury_dashboard_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )
    arbitrage = dashboard_result.snapshot.arbitrage_ranking[0]
    browser_candidate = dashboard_result.snapshot.candidates_by_id[arbitrage.external_id]

    opportunity_store = SQLiteOpportunityStore(database_path=tmp_path / "brand_profit.db")
    saved = opportunity_store.save_arbitrage(arbitrage)

    assert direct_candidate.profit_result is not None
    assert browser_candidate.profit_result is not None
    assert saved.estimated_profit == float(browser_candidate.profit_result.profit_jpy)
    assert saved.profit_margin == float(browser_candidate.profit_result.profit_margin)
    assert saved.decision == browser_candidate.buy_decision.decision.value
    assert browser_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert browser_candidate.profit_result.roi == direct_candidate.profit_result.roi


def test_storage_pipeline_from_browser_search_to_sqlite(tmp_path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "brand_profit.db"))
    client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )

    store: DashboardResultStore = client.app.state.result_store
    snapshot = store.get()
    assert snapshot is not None
    product_id = snapshot.arbitrage_ranking[0].external_id
    candidate = snapshot.candidates_by_id[product_id]
    assert candidate.profit_result is not None

    client.post(f"/opportunities/{product_id}/save")
    saved_items = client.app.state.opportunity_store.list_all()

    assert len(saved_items) == 1
    assert saved_items[0].estimated_profit == float(candidate.profit_result.profit_jpy)
    assert saved_items[0].decision == candidate.buy_decision.decision.value

    saved_page = client.get("/saved")
    assert saved_page.status_code == 200
    assert "保存済み候補" in saved_page.text
