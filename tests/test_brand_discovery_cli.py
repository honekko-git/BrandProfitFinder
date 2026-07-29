"""Tests for tier-based brand discovery CLI behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from profit_discovery.brand_catalog import BrandCatalog, BrandProfile, BrandTier
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_discovery_parser,
    resolve_discovery_brands,
    run_discovery_cli,
    run_discovery_command,
)
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult


def test_build_discovery_parser_accepts_tier_argument() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--tier", "S"])

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.tier == "S"
    assert options.brands == ["Chanel", "Louis Vuitton", "Miu Miu", "Hermes", "Coach"]


def test_resolve_discovery_brands_prefers_explicit_brands_over_tier() -> None:
    brands = resolve_discovery_brands(
        brands=["Chanel", "Gucci"],
        tier="S",
    )

    assert brands == ["Chanel", "Gucci"]


def test_resolve_discovery_brands_uses_tier_when_brands_not_provided() -> None:
    brands = resolve_discovery_brands(tier="A")

    assert brands == ["Dior", "Celine", "Loewe", "Bottega Veneta", "Prada"]


def test_resolve_discovery_brands_returns_empty_without_inputs() -> None:
    assert resolve_discovery_brands() == []


def test_run_discovery_command_with_tier_resolves_catalog_brands() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=(),
        failed_brands=(),
        total_candidates=0,
    )

    run_discovery_command(
        DiscoveryCommandOptions(brands=["Chanel", "Louis Vuitton", "Miu Miu", "Hermes", "Coach"], tier="S"),
        runner=runner,
    )

    request = runner.run.call_args.args[0]
    assert request.brands == ["Chanel", "Louis Vuitton", "Miu Miu", "Hermes", "Coach"]


def test_existing_brands_cli_remains_compatible() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--brands", "CHANEL,LouisVuitton"])

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.brands == ["CHANEL", "Louis Vuitton"]
    assert options.tier is None


def test_run_discovery_cli_accepts_tier_without_brands() -> None:
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
        assert run_discovery_cli(["--tier", "S"]) == 0

    options = command_mock.call_args.args[0]
    assert options.brands == ["Chanel", "Louis Vuitton", "Miu Miu", "Hermes", "Coach"]


def test_run_discovery_cli_still_accepts_explicit_brands() -> None:
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
        assert run_discovery_cli(["--brands", "Chanel,Gucci"]) == 0

    options = command_mock.call_args.args[0]
    assert options.brands == ["Chanel", "Gucci"]


def test_custom_catalog_can_drive_tier_resolution() -> None:
    catalog = BrandCatalog(
        brands=[
            BrandProfile(name="Sample S Brand", tier=BrandTier.S.value),
        ],
    )

    brands = resolve_discovery_brands(tier="S", catalog=catalog)

    assert brands == ["Sample S Brand"]
