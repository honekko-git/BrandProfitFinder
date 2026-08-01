"""CLI entry point for multi-brand discovery."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TextIO

from config.settings import OUTPUT_DIR
from excel.exporter import ExcelExporter
from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketClientResolution,
    DomesticMarketClientResolver,
    DomesticMarketRuntimeConfig,
    DomesticMarketSource,
    FakeMercariDomesticMarketClient,
    MarketExecutionResult,
    read_market_execution,
    requested_mode_from_config,
    resolve_client_name,
    YahooAuctionTransport,
)
from product_identity.duplicate_resolver import DuplicateResolver
from product_identity.identity_resolver import ProductIdentityResolver
from profit_discovery.brand_catalog import BrandCatalog
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.category_catalog import BrandCategoryResolver, CategoryCatalog
from profit_discovery.category_catalog.models import BrandCategorySearchTarget
from profit_discovery.cli.demand_export import append_demand_opportunity_ranking_sheet
from profit_discovery.cli.discovery_output import render_discovery_run
from profit_discovery.cli.opportunity_export import append_opportunity_ranking_sheet
from profit_discovery.cli.showcase_export import (
    append_showcase_sheet,
    build_showcase_opportunities_from_ranking,
)
from profit_discovery.discovery_runner import DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import (
    MultiBrandDiscoveryRequest,
    MultiBrandDiscoveryResult,
    MultiBrandDiscoveryRunner,
)
from profit_discovery.opportunity.identity_pipeline import build_identity_demand_integrated_ranking
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_discovery.profit_ranking import rank_used_luxury_products
from profit_discovery.arbitrage import create_arbitrage_ranking
from profit_intelligence.demand.lookup import DemandLookup
from profit_intelligence.demand.resolver import DemandQueryResolver
from supplier.config import SupplierRuntimeConfig
from supplier.factory import resolve_supplier_client

logger = logging.getLogger(__name__)

DISCOVERY_REPORT_FILENAME = "discovery_report.xlsx"


@dataclass(frozen=True, slots=True)
class DiscoveryCommandOptions:
    """Parsed CLI options for the discovery command."""

    brands: list[str]
    category: str | None = None
    keyword: str | None = None
    tier: str | None = None
    category_priority: str | None = None
    export: bool = False
    live_market: bool = False
    used_luxury: bool = False
    max_results_per_brand: int = 20
    search_targets: tuple[BrandCategorySearchTarget, ...] | None = None

    @classmethod
    def from_namespace(
        cls,
        namespace: argparse.Namespace,
        *,
        catalog: BrandCatalog | None = None,
        category_catalog: CategoryCatalog | None = None,
        resolver: BrandCategoryResolver | None = None,
        used_luxury_config: UsedLuxuryModeConfig | None = None,
    ) -> DiscoveryCommandOptions:
        used_luxury = bool(getattr(namespace, "used_luxury", False))
        active_used_luxury_config = (
            used_luxury_config or UsedLuxuryModeConfig.default()
            if used_luxury
            else None
        )
        explicit_brands = parse_brands(namespace.brands) if namespace.brands else []
        tier = namespace.tier
        if used_luxury and not explicit_brands and not tier:
            tier = "S"
        brands = resolve_discovery_brands(
            brands=explicit_brands,
            tier=tier,
            catalog=catalog,
            used_luxury_config=active_used_luxury_config,
        )
        if active_used_luxury_config is not None:
            brands = active_used_luxury_config.filter_brands(brands)
        search_targets = build_discovery_search_targets(
            brands,
            category_priority=namespace.category_priority,
            category_catalog=category_catalog,
            resolver=resolver,
            used_luxury_config=active_used_luxury_config,
        )
        return cls(
            brands=brands,
            category=namespace.category,
            keyword=namespace.keyword,
            tier=tier,
            category_priority=namespace.category_priority,
            export=bool(namespace.export),
            live_market=bool(namespace.live_market),
            used_luxury=used_luxury,
            max_results_per_brand=namespace.max_results_per_brand,
            search_targets=search_targets,
        )


def build_discovery_parser() -> argparse.ArgumentParser:
    """Build argument parser for `python main.py discovery`."""
    parser = argparse.ArgumentParser(
        description="Run multi-brand overseas supplier discovery against domestic market fixtures.",
    )
    parser.add_argument(
        "--brands",
        default=None,
        help="Comma-separated brand list (example: CHANEL,LouisVuitton,Hermes)",
    )
    parser.add_argument(
        "--tier",
        default=None,
        choices=["S", "A", "B"],
        help="Discover all enabled brands in a catalog tier (example: S)",
    )
    parser.add_argument("--category", default=None, help="Optional category filter")
    parser.add_argument(
        "--category-priority",
        default=None,
        choices=["HIGH", "MEDIUM", "LOW"],
        help="Discover enabled categories for the selected priority (example: HIGH)",
    )
    parser.add_argument("--keyword", default=None, help="Optional keyword filter")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export ranked discovery results to the Discovery Excel report",
    )
    parser.add_argument(
        "--live-market",
        action="store_true",
        help="Use Yahoo Auction live HTTP transport instead of fixture market data",
    )
    parser.add_argument(
        "--used-luxury",
        action="store_true",
        help="Run discovery in used luxury mode with Yahoo Auction and Mercari markets",
    )
    parser.add_argument(
        "--max-results-per-brand",
        type=int,
        default=20,
        help="Maximum supplier products to evaluate per brand",
    )
    return parser


def parse_brands(raw: str) -> list[str]:
    """Parse comma-separated CLI brand values into normalized brand names."""
    brands: list[str] = []
    for part in raw.split(","):
        normalized = _normalize_brand_name(part)
        if normalized:
            brands.append(normalized)
    return brands


def resolve_discovery_brands(
    *,
    brands: list[str] | None = None,
    tier: str | None = None,
    catalog: BrandCatalog | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
) -> list[str]:
    """Resolve discovery target brands using explicit brands first, then tier."""
    if brands:
        return brands
    if tier:
        if used_luxury_config is not None:
            return used_luxury_config.brand_names_for_tier(tier)
        active_catalog = catalog or BrandCatalog.default()
        return active_catalog.brand_names_for_tier(tier)
    return []


def build_discovery_search_targets(
    brands: list[str],
    *,
    category_priority: str | None = None,
    category_catalog: CategoryCatalog | None = None,
    resolver: BrandCategoryResolver | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
):
    """Build brand-category search targets when a category priority is selected."""
    if not category_priority or not brands:
        return None

    if used_luxury_config is not None:
        categories = used_luxury_config.get_category_profiles_for_priority(category_priority)
    else:
        active_catalog = category_catalog or CategoryCatalog.default()
        categories = active_catalog.get_by_priority(category_priority)
    active_resolver = resolver or BrandCategoryResolver()
    targets = active_resolver.resolve(brands, categories)
    return targets or None


def build_default_supplier_client(
    supplier_name: str = "fashionphile",
    *,
    config: SupplierRuntimeConfig | None = None,
):
    """Resolve the default supplier client for discovery runtime selection."""
    return resolve_supplier_client(
        supplier_name,
        config=config or SupplierRuntimeConfig.default(),
    )


def build_domestic_market_runtime_config(*, live_market: bool = False) -> DomesticMarketRuntimeConfig:
    """Build domestic market runtime config from discovery CLI mode."""
    if live_market:
        return DomesticMarketRuntimeConfig.from_cli_live_market()
    return DomesticMarketRuntimeConfig.default()


def resolve_market_mode_label(*, live_market: bool) -> str:
    """Return the CLI market mode label."""
    return "LIVE" if live_market else "FIXTURE"


def resolve_market_source_label(*, live_market: bool) -> str:
    """Return the showcase market source label."""
    return "Yahoo Auction LIVE" if live_market else "Fixture"


def resolve_domestic_market_client(
    market_config: DomesticMarketRuntimeConfig | None = None,
    *,
    injected_transport: YahooAuctionTransport | None = None,
) -> DomesticMarketClientResolution:
    """Resolve one domestic market client and execution metadata."""
    runtime_config = market_config or DomesticMarketRuntimeConfig.default()
    resolution = DomesticMarketClientResolver(config=runtime_config).resolve_yahoo_auction(
        injected_transport=injected_transport,
    )
    if resolution.client is not None:
        return resolution

    fallback = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig.default(),
    ).resolve_yahoo_auction()
    if fallback.client is None:
        raise ValueError("Unable to resolve domestic market client")

    return DomesticMarketClientResolution(
        market_name=fallback.market_name,
        client=fallback.client,
        mode=fallback.mode,
        execution=MarketExecutionResult(
            requested_mode=requested_mode_from_config(runtime_config),
            actual_source="Fixture",
            fallback_used=True,
            client_name=resolve_client_name(fallback.client),
        ),
    )


def read_runtime_market_execution(
    runner: MultiBrandDiscoveryRunner,
    *,
    fallback_resolution: DomesticMarketClientResolution | None = None,
) -> MarketExecutionResult:
    """Read actual market execution truth after a discovery run."""
    connector = runner.discovery_runner.market_connector
    aggregator = connector.market_aggregator
    if aggregator is not None and aggregator.clients:
        execution = read_market_execution(aggregator.clients[0][1])
        if execution is not None:
            return execution

    if fallback_resolution is not None and isinstance(
        fallback_resolution.execution,
        MarketExecutionResult,
    ):
        return fallback_resolution.execution

    return MarketExecutionResult(
        requested_mode="FIXTURE",
        actual_source="Fixture",
        fallback_used=False,
        client_name="YahooAuctionDomesticMarketClient",
    )


def build_default_market_aggregator(
    market_config: DomesticMarketRuntimeConfig | None = None,
    *,
    injected_transport: YahooAuctionTransport | None = None,
    used_luxury: bool = False,
) -> tuple[DomesticMarketAggregator, DomesticMarketClientResolution]:
    """Build the default domestic market aggregator for discovery CLI runs."""
    resolution = resolve_domestic_market_client(
        market_config,
        injected_transport=injected_transport,
    )
    assert resolution.client is not None
    clients = [
        (
            DomesticMarketSource(name="yahoo_auction", enabled=True),
            resolution.client,
        ),
    ]
    if used_luxury:
        clients.append(
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(),
            ),
        )
    aggregator = DomesticMarketAggregator(clients=clients)
    return aggregator, resolution


def build_default_discovery_runner(
    *,
    supplier_name: str = "fashionphile",
    config: SupplierRuntimeConfig | None = None,
    market_config: DomesticMarketRuntimeConfig | None = None,
    injected_transport: YahooAuctionTransport | None = None,
    used_luxury: bool = False,
) -> MultiBrandDiscoveryRunner:
    """Build the default multi-brand discovery runner."""
    runtime_config = config or SupplierRuntimeConfig.default()
    supplier_client = build_default_supplier_client(supplier_name, config=runtime_config)
    if supplier_client is None:
        raise ValueError(f"Unable to resolve supplier client: {supplier_name}")
    aggregator, market_resolution = build_default_market_aggregator(
        market_config,
        injected_transport=injected_transport,
        used_luxury=used_luxury,
    )
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_aggregator=aggregator,
        ),
    )
    runner = MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)
    runner.market_resolution = market_resolution  # type: ignore[attr-defined]
    return runner


def build_production_discovery_pipeline(
    result: MultiBrandDiscoveryResult,
    *,
    identity_resolver: ProductIdentityResolver | None = None,
    duplicate_resolver: DuplicateResolver | None = None,
    demand_resolver: DemandQueryResolver | None = None,
    lookup: DemandLookup | None = None,
    scorer: DemandIntegratedOpportunityScorer | None = None,
) -> tuple[DemandIntegratedOpportunityResult, ...]:
    """Run identity resolution, duplicate merge, and demand-integrated ranking."""
    ranked = build_identity_demand_integrated_ranking(
        result.ranked_candidates,
        identity_resolver=identity_resolver,
        duplicate_resolver=duplicate_resolver,
        demand_resolver=demand_resolver,
        lookup=lookup,
        scorer=scorer,
    )
    return tuple(ranked)


def run_discovery_command(
    options: DiscoveryCommandOptions,
    *,
    runner: MultiBrandDiscoveryRunner | None = None,
    output: TextIO | None = None,
    injected_transport: YahooAuctionTransport | None = None,
) -> MultiBrandDiscoveryResult:
    """Execute multi-brand discovery using existing library components."""
    market_config = build_domestic_market_runtime_config(live_market=options.live_market)
    used_luxury_config = UsedLuxuryModeConfig.default() if options.used_luxury else None
    active_runner = runner or build_default_discovery_runner(
        market_config=market_config,
        injected_transport=injected_transport,
        used_luxury=options.used_luxury,
    )
    market_resolution = getattr(active_runner, "market_resolution", None)
    if not isinstance(market_resolution, DomesticMarketClientResolution):
        market_resolution = None
    request = MultiBrandDiscoveryRequest(
        brands=options.brands,
        category=options.category,
        keyword=options.keyword,
        max_results_per_brand=options.max_results_per_brand,
        search_targets=options.search_targets,
    )
    result = active_runner.run(request)
    ranked_demand_opportunities = build_production_discovery_pipeline(result)
    result = replace(result, ranked_demand_opportunities=ranked_demand_opportunities)
    used_luxury_profit_ranking = None
    used_luxury_arbitrage_ranking = None
    if used_luxury_config is not None:
        used_luxury_profit_ranking = rank_used_luxury_products(
            ranked_demand_opportunities,
            config=used_luxury_config,
        )
        used_luxury_arbitrage_ranking = create_arbitrage_ranking(
            ranked_demand_opportunities,
            config=used_luxury_config,
        )
    market_execution = read_runtime_market_execution(
        active_runner,
        fallback_resolution=market_resolution,
    )
    market_execution = MarketExecutionResult(
        requested_mode=resolve_market_mode_label(live_market=options.live_market),
        actual_source=market_execution.actual_source,
        fallback_used=market_execution.fallback_used,
        client_name=market_execution.client_name,
    )

    export_path: Path | None = None
    if options.export:
        export_path = export_discovery_report(
            result,
            market_execution=market_execution,
            used_luxury_config=used_luxury_config,
            used_luxury_profit_ranking=used_luxury_profit_ranking,
            used_luxury_arbitrage_ranking=used_luxury_arbitrage_ranking,
        )
        if export_path is not None:
            logger.info("Discovery Excel report exported: %s", export_path)
        else:
            logger.warning("Discovery export skipped: no profitable candidates to export")

    render_discovery_run(
        result,
        brands=options.brands,
        export_path=export_path,
        ranked_opportunities=list(result.ranked_opportunities),
        ranked_demand_opportunities=list(result.ranked_demand_opportunities),
        used_luxury_profit_ranking=used_luxury_profit_ranking,
        used_luxury_arbitrage_ranking=used_luxury_arbitrage_ranking,
        market_execution=market_execution,
        used_luxury_config=used_luxury_config,
        output=output or sys.stdout,
    )

    logger.info(
        "Discovery completed (brands=%d, successful=%d, failed=%d, candidates=%d)",
        len(options.brands),
        len(result.successful_brands),
        len(result.failed_brands),
        result.total_candidates,
    )
    return result


def export_discovery_report(
    result: MultiBrandDiscoveryResult,
    *,
    output_dir: Path | str | None = None,
    filename: str = DISCOVERY_REPORT_FILENAME,
    market_execution: MarketExecutionResult | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
    used_luxury_profit_ranking: list | None = None,
    used_luxury_arbitrage_ranking: list | None = None,
) -> Path | None:
    """Export ranked discovery candidates to the Discovery Excel report."""
    price_results = [
        candidate.profit_result
        for candidate in result.ranked_candidates
        if candidate.profit_result is not None
    ]
    if not price_results:
        return None

    exporter = ExcelExporter(
        output_dir=Path(output_dir) if output_dir is not None else OUTPUT_DIR,
        filename=filename,
    )
    export_path = exporter.export_price_results(price_results)
    append_opportunity_ranking_sheet(export_path, list(result.ranked_opportunities))
    append_demand_opportunity_ranking_sheet(export_path, list(result.ranked_demand_opportunities))
    append_showcase_sheet(
        export_path,
        build_showcase_opportunities_from_ranking(
            result.ranked_demand_opportunities,
            market_execution=market_execution,
            used_luxury_config=used_luxury_config,
            profit_ranking=used_luxury_profit_ranking,
            arbitrage_ranking=used_luxury_arbitrage_ranking,
        ),
    )
    return export_path


def run_discovery_cli(argv: list[str] | None = None) -> int:
    """Parse discovery CLI arguments and execute the command."""
    parser = build_discovery_parser()
    namespace = parser.parse_args(argv)
    if not namespace.brands and not namespace.tier and not namespace.used_luxury:
        parser.error("Either --brands, --tier, or --used-luxury must be specified")
    options = DiscoveryCommandOptions.from_namespace(namespace)
    if not options.brands:
        parser.error("No discovery brands resolved from the provided arguments")
    run_discovery_command(options)
    return 0


def _normalize_brand_name(raw: str) -> str:
    brand = raw.strip()
    if not brand:
        return ""
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", brand)
