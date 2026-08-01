"""Dashboard pipeline that reuses the existing Used Luxury discovery stack."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from profit_discovery.arbitrage.market_listings import resolve_purchase_listing
from profit_discovery.arbitrage import create_arbitrage_ranking
from profit_discovery.arbitrage.resolver import ArbitrageOpportunityResolver
from profit_discovery.cli.discovery_command import (
    build_default_discovery_runner,
    build_domestic_market_runtime_config,
    build_production_discovery_pipeline,
)
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.profit_ranking import rank_used_luxury_products
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.execution import MarketConnectorExecutionResult
from marketplace.connectors.models import MarketListing
from marketplace.connectors.resolver import MarketConnectorResolver

from app.store import DashboardResultStore, DashboardSearchSnapshot


@dataclass(frozen=True, slots=True)
class DashboardPipelineResult:
    """Output from one dashboard search execution."""

    snapshot: DashboardSearchSnapshot
    total_candidates: int


def run_used_luxury_dashboard_search(
    *,
    brand: str,
    category: str,
    market_mode: str = "FIXTURE",
    max_results_per_brand: int = 20,
    runner: MultiBrandDiscoveryRunner | None = None,
) -> DashboardPipelineResult:
    """Run the existing Used Luxury pipeline for the browser dashboard."""
    live_market = market_mode.strip().upper() == "LIVE"
    used_luxury_config = UsedLuxuryModeConfig.default()
    market_config = build_domestic_market_runtime_config(live_market=live_market)
    connector_config = MarketConnectorConfig.from_env().with_mode(market_mode)
    connector_resolver = MarketConnectorResolver(connector_config)
    active_runner = runner or build_default_discovery_runner(
        market_config=market_config,
        used_luxury=True,
    )
    keyword = category.strip().lower()
    request = MultiBrandDiscoveryRequest(
        brands=[brand.strip()],
        category=category.strip() or None,
        keyword=keyword or None,
        max_results_per_brand=max_results_per_brand,
    )
    result = active_runner.run(request)
    ranked_demand_opportunities = build_production_discovery_pipeline(result)
    profit_ranking = rank_used_luxury_products(
        ranked_demand_opportunities,
        config=used_luxury_config,
    )
    connector_executions: dict[str, MarketConnectorExecutionResult] = {}
    arbitrage_ranking = create_arbitrage_ranking(
        ranked_demand_opportunities,
        config=used_luxury_config,
        resolver=ArbitrageOpportunityResolver(
            config=used_luxury_config,
            market_connector_resolver=connector_resolver,
        ),
    )
    candidates_by_id = {
        candidate.supplier_product.external_id: candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    }
    listings_by_id = _build_listings_by_id(
        arbitrage_ranking,
        candidates_by_id,
        connector_resolver=connector_resolver,
        connector_executions=connector_executions,
    )
    snapshot = DashboardSearchSnapshot(
        brand=brand.strip(),
        category=category.strip(),
        market_mode=market_mode.strip().upper(),
        arbitrage_ranking=arbitrage_ranking,
        profit_ranking=profit_ranking,
        candidates_by_id=candidates_by_id,
        listings_by_id=listings_by_id,
        connector_executions=connector_executions,
    )
    return DashboardPipelineResult(
        snapshot=snapshot,
        total_candidates=result.total_candidates,
    )


def execute_dashboard_search(
    store: DashboardResultStore,
    *,
    brand: str,
    category: str,
    market_mode: str = "FIXTURE",
    runner: MultiBrandDiscoveryRunner | None = None,
) -> DashboardPipelineResult:
    """Execute dashboard search and persist the latest snapshot."""
    pipeline_result = run_used_luxury_dashboard_search(
        brand=brand,
        category=category,
        market_mode=market_mode,
        runner=runner,
    )
    store.save(pipeline_result.snapshot)
    return pipeline_result


def format_jpy(value: Decimal | int | float | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} JPY"


def format_listing_price(listing: MarketListing | None) -> str:
    if listing is None:
        return "N/A"
    if listing.currency.upper() == "JPY":
        return format_jpy(listing.price)
    return f"{listing.price:,} {listing.currency}"


def format_percent(value: Decimal | float | None) -> str:
    if value is None:
        return "N/A"
    normalized = float(value)
    if normalized == int(normalized):
        return f"{int(normalized)}%"
    return f"{normalized:.1f}%"


def _build_listings_by_id(
    arbitrage_ranking,
    candidates_by_id: dict[str, DiscoveryCandidateResult],
    *,
    connector_resolver: MarketConnectorResolver,
    connector_executions: dict[str, MarketConnectorExecutionResult],
) -> dict[str, MarketListing]:
    listings_by_id: dict[str, MarketListing] = {}
    for item in arbitrage_ranking:
        candidate = candidates_by_id.get(item.external_id)
        if candidate is None:
            continue
        listing = resolve_purchase_listing(
            candidate.supplier_product,
            connector_resolver=connector_resolver,
            execution_sink=connector_executions,
        )
        if listing is not None:
            listings_by_id[item.external_id] = listing
    return listings_by_id
