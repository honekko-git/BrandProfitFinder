"""Tests for demand analyzer fixture and batch processing."""

from __future__ import annotations

from pathlib import Path

from profit_intelligence.demand import DemandAnalyzer


def test_demand_analyzer_parses_fixture() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    analyzer = DemandAnalyzer(fixture_dir=fixture_dir)

    profile = analyzer.analyze_fixture("chanel_wallet.json")

    assert profile.query == "Chanel Wallet"
    assert profile.period_days == 30
    assert profile.sold_count == 35
    assert profile.average_sold_price_jpy == 160000.0
    assert profile.sell_through_rate == 0.75
    assert profile.demand_score == profile.calculate_demand_score()
    assert 75.0 <= profile.demand_score <= 95.0


def test_demand_analyzer_batch_analyze_processes_multiple_products() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    analyzer = DemandAnalyzer(fixture_dir=fixture_dir)
    products = [
        analyzer._load_fixture("chanel_wallet.json"),
        analyzer._load_fixture("coach_wallet.json"),
    ]

    profiles = analyzer.batch_analyze(products)

    assert len(profiles) == 2
    assert profiles[0].query == "Chanel Wallet"
    assert profiles[1].query == "Coach Wallet"
    assert profiles[0].demand_score > profiles[1].demand_score
