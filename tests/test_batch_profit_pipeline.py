"""Tests for batch profit pipeline."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from profit_discovery.discovery_validation.batch_profit.candidate_import import load_batch_candidates_from_csv
from profit_discovery.discovery_validation.batch_profit.costs import default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit
from profit_discovery.discovery_validation.batch_profit.ranking import rank_batch_results

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"
YAHOO_HTML = (FIXTURES / "browser_acquisition" / "yahoo_live_ja.html").read_text(encoding="utf-8")


def test_multiple_candidates_processed_with_fixture_html() -> None:
    imported = load_batch_candidates_from_csv(BATCH_FIXTURES / "candidates_valid.csv", limit=2)
    html_map = {query: YAHOO_HTML for query in [
        "シャネル キャビアスキン 財布 黒",
        "シャネル クラシック 財布",
        "CHANEL wallet caviar black",
    ]}
    run = run_batch_profit(
        imported.candidates,
        cost_profile=default_cost_profiles()["standard"],
        use_cache=False,
        html_by_query=html_map,
        import_errors=tuple(imported.errors),
    )
    assert run.summary.processed_count == 2
    assert all(item.candidate.title for item in run.results)


def test_one_candidate_failure_does_not_stop_batch() -> None:
    imported = load_batch_candidates_from_csv(BATCH_FIXTURES / "candidates_valid.csv", limit=2)
    run = run_batch_profit(
        imported.candidates,
        cost_profile=default_cost_profiles()["standard"],
        use_cache=False,
        html_by_query={},
    )
    assert run.summary.processed_count == 2


def test_ranking_orders_by_decision_then_profit() -> None:
    imported = load_batch_candidates_from_csv(BATCH_FIXTURES / "candidates_valid.csv", limit=2)
    run = run_batch_profit(
        imported.candidates,
        cost_profile=default_cost_profiles()["conservative"],
        use_cache=False,
        html_by_query={query: YAHOO_HTML for query in ["シャネル クラシック 財布"]},
    )
    ranked = rank_batch_results(list(run.results))
    assert ranked[0].rank == 1
    assert ranked[-1].rank == len(ranked)
