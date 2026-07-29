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
    DomesticMarketSource,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from product_identity.duplicate_resolver import DuplicateResolver
from product_identity.identity_resolver import ProductIdentityResolver
from profit_discovery.brand_catalog import BrandCatalog
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
    ) -> DiscoveryCommandOptions:
        explicit_brands = parse_brands(namespace.brands) if namespace.brands else []
        tier = namespace.tier
        brands = resolve_discovery_brands(
            brands=explicit_brands,
            tier=tier,
            catalog=catalog,
        )
        search_targets = build_discovery_search_targets(
            brands,
            category_priority=namespace.category_priority,
            category_catalog=category_catalog,
            resolver=resolver,
        )
        return cls(
            brands=brands,
            category=namespace.category,
            keyword=namespace.keyword,
            tier=tier,
            category_priority=namespace.category_priority,
            export=bool(namespace.export),
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
) -> list[str]:
    """Resolve discovery target brands using explicit brands first, then tier."""
    if brands:
        return brands
    if tier:
        active_catalog = catalog or BrandCatalog.default()
        return active_catalog.brand_names_for_tier(tier)
    return []


def build_discovery_search_targets(
    brands: list[str],
    *,
    category_priority: str | None = None,
    category_catalog: CategoryCatalog | None = None,
    resolver: BrandCategoryResolver | None = None,
):
    """Build brand-category search targets when a category priority is selected."""
    if not category_priority or not brands:
        return None

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


def build_default_discovery_runner(
    *,
    supplier_name: str = "fashionphile",
    config: SupplierRuntimeConfig | None = None,
) -> MultiBrandDiscoveryRunner:
    """Build the default multi-brand discovery runner."""
    runtime_config = config or SupplierRuntimeConfig.default()
    supplier_client = build_default_supplier_client(supplier_name, config=runtime_config)
    if supplier_client is None:
        raise ValueError(f"Unable to resolve supplier client: {supplier_name}")
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_aggregator=DomesticMarketAggregator(
                clients=[
                    (
                        DomesticMarketSource(name="yahoo_auction", enabled=True),
                        YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
                    ),
                ],
            ),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


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
) -> MultiBrandDiscoveryResult:
    """Execute multi-brand discovery using existing library components."""
    active_runner = runner or build_default_discovery_runner()
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

    export_path: Path | None = None
    if options.export:
        export_path = export_discovery_report(result)
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
        build_showcase_opportunities_from_ranking(result.ranked_demand_opportunities),
    )
    return export_path


def run_discovery_cli(argv: list[str] | None = None) -> int:
    """Parse discovery CLI arguments and execute the command."""
    parser = build_discovery_parser()
    namespace = parser.parse_args(argv)
    if not namespace.brands and not namespace.tier:
        parser.error("Either --brands or --tier must be specified")
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
