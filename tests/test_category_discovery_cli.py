"""Tests for category-priority discovery CLI behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_discovery_parser,
    build_discovery_search_targets,
    resolve_discovery_brands,
    run_discovery_cli,
    run_discovery_command,
)
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult


def test_build_discovery_parser_accepts_category_priority() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--tier", "S", "--category-priority", "HIGH"])

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.tier == "S"
    assert options.category_priority == "HIGH"
    assert options.brands == ["Chanel", "Louis Vuitton", "Miu Miu", "Hermes", "Coach"]
    assert options.search_targets is not None
    assert len(options.search_targets) == 25
    assert options.search_targets[0].query == "Chanel Wallet"


def test_build_discovery_search_targets_uses_resolved_brands() -> None:
    brands = resolve_discovery_brands(tier="A")
    targets = build_discovery_search_targets(brands, category_priority="HIGH")

    assert targets is not None
    assert len(targets) == len(brands) * 5
    assert targets[0].brand == "Dior"
    assert targets[0].category == "Wallet"


def test_explicit_brands_take_priority_over_tier_with_category_filter() -> None:
    brands = resolve_discovery_brands(brands=["Chanel"], tier="S")
    targets = build_discovery_search_targets(brands, category_priority="HIGH")

    assert brands == ["Chanel"]
    assert targets is not None
    assert len(targets) == 5
    assert all(target.brand == "Chanel" for target in targets)


def test_existing_brands_cli_remains_compatible_without_category_priority() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--brands", "Chanel,Gucci"])

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.brands == ["Chanel", "Gucci"]
    assert options.category_priority is None
    assert options.search_targets is None


def test_run_discovery_command_passes_search_targets_to_runner() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=(),
        failed_brands=(),
        total_candidates=0,
    )
    options = DiscoveryCommandOptions.from_namespace(
        build_discovery_parser().parse_args(["--brands", "Chanel", "--category-priority", "HIGH"]),
    )

    run_discovery_command(options, runner=runner)

    request = runner.run.call_args.args[0]
    assert request.search_targets is not None
    assert len(request.search_targets) == 5
    assert request.search_targets[0].query == "Chanel Wallet"


def test_run_discovery_cli_accepts_tier_with_category_priority() -> None:
    with patch(
        "profit_discovery.cli.discovery_command.run_discovery_command",
        return_value=MultiBrandDiscoveryResult(
            results=(),
            ranked_candidates=(),
            ranked_opportunities=(),
            successful_brands=(),
            failed_brands=(),
            total_candidates=0,
        ),
    ) as command_mock:
        assert run_discovery_cli(["--tier", "S", "--category-priority", "HIGH"]) == 0

    options = command_mock.call_args.args[0]
    assert options.category_priority == "HIGH"
    assert options.search_targets is not None
