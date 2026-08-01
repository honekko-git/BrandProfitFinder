"""Pipeline tests for used luxury arbitrage integration."""

from __future__ import annotations

import io

from profit_discovery.arbitrage import create_arbitrage_ranking
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    run_discovery_command,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.showcase.formatter import ShowcaseFormatter


def test_used_luxury_arbitrage_pipeline_preserves_profit_integrity() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    options = DiscoveryCommandOptions(
        brands=["Chanel"],
        keyword="wallet",
        max_results_per_brand=1,
        used_luxury=True,
    )

    direct_result = MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=options.brands,
            keyword=options.keyword,
            max_results_per_brand=options.max_results_per_brand,
        ),
    )
    output = io.StringIO()
    cli_result = run_discovery_command(
        options,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
        output=output,
    )

    direct_candidate = next(
        item for item in direct_result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )
    cli_candidate = next(
        item for item in cli_result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )

    assert direct_candidate.profit_result is not None
    assert cli_candidate.profit_result is not None
    assert cli_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert cli_candidate.profit_result.profit_margin == direct_candidate.profit_result.profit_margin
    assert cli_candidate.profit_result.roi == direct_candidate.profit_result.roi
    assert direct_candidate.buy_decision is not None
    assert cli_candidate.buy_decision is not None
    assert cli_candidate.buy_decision.decision == direct_candidate.buy_decision.decision


def test_used_luxury_arbitrage_pipeline_cli_shows_arbitrage_ranking() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
            used_luxury=True,
        ),
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
        output=output,
    )

    rendered = output.getvalue()
    assert "中古高級品 裁定順位" in rendered
    assert "仕入先:" in rendered
    assert "販売市場:" in rendered
    assert "推定利益:" in rendered

    arbitrage_ranking = create_arbitrage_ranking(
        result.ranked_demand_opportunities,
        config=UsedLuxuryModeConfig.default(),
    )
    assert arbitrage_ranking
    assert arbitrage_ranking[0].recommendation_rank == 1


def test_used_luxury_arbitrage_pipeline_showcase_includes_arbitrage_fields() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
            used_luxury=True,
        ),
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
        output=io.StringIO(),
    )

    arbitrage_ranking = create_arbitrage_ranking(
        result.ranked_demand_opportunities,
        config=UsedLuxuryModeConfig.default(),
    )
    showcase_items = ShowcaseFormatter().to_showcase_opportunities(
        result.ranked_demand_opportunities,
        used_luxury_config=UsedLuxuryModeConfig.default(),
        arbitrage_ranking=arbitrage_ranking,
    )

    assert showcase_items
    item = showcase_items[0]
    assert item.purchase_source
    assert item.purchase_url
    assert item.selling_market
    assert item.selling_url
    assert item.estimated_profit is not None
    assert item.profit_jpy is not None
    assert item.decision in {"BUY", "HOLD", "PASS"}
