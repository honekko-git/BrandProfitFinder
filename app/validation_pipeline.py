"""Profit validation discovery pipeline for the browser dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from profit_discovery.arbitrage.market_listings import resolve_selling_listing
from profit_discovery.discovery_validation import create_validation_ranking
from profit_discovery.discovery_validation.models import ValidationConfig, ValidationOpportunity
from marketplace.connectors.resolver import MarketConnectorResolver

from app.pipeline import run_used_luxury_dashboard_search
from app.store import ValidationResultStore, ValidationSearchSnapshot
from profit_discovery.multi_brand import MultiBrandDiscoveryRunner


@dataclass(frozen=True, slots=True)
class ValidationPipelineResult:
    """Output from one profit validation search."""

    snapshot: ValidationSearchSnapshot
    total_candidates: int
    validation_count: int


def run_profit_validation_search(
    *,
    brand: str,
    category: str,
    market_mode: str = "FIXTURE",
    max_results_per_brand: int = 20,
    runner: MultiBrandDiscoveryRunner | None = None,
    config: ValidationConfig | None = None,
) -> ValidationPipelineResult:
    """Run overseas purchase vs domestic selling validation for Tier S brands."""
    active_config = config or ValidationConfig()
    normalized_brand = brand.strip()
    normalized_category = category.strip()
    if not active_config.is_allowed_brand(normalized_brand):
        raise ValueError(f"Brand is not supported for validation: {normalized_brand}")
    if not active_config.is_allowed_category(normalized_category):
        raise ValueError(f"Category is not supported for validation: {normalized_category}")

    dashboard_result = run_used_luxury_dashboard_search(
        brand=normalized_brand,
        category=normalized_category,
        market_mode=market_mode,
        max_results_per_brand=max_results_per_brand,
        runner=runner,
    )
    connector_resolver = MarketConnectorResolver()
    selling_listings_by_id = _build_selling_listings_by_id(
        dashboard_result.snapshot.arbitrage_ranking,
        connector_resolver=connector_resolver,
    )
    validation_ranking = create_validation_ranking(
        dashboard_result.snapshot.arbitrage_ranking,
        config=active_config,
        selling_listings_by_id=selling_listings_by_id,
    )
    snapshot = ValidationSearchSnapshot(
        brand=normalized_brand,
        category=normalized_category,
        market_mode=market_mode.strip().upper(),
        validation_ranking=validation_ranking,
        candidates_by_id=dict(dashboard_result.snapshot.candidates_by_id),
    )
    return ValidationPipelineResult(
        snapshot=snapshot,
        total_candidates=dashboard_result.total_candidates,
        validation_count=len(validation_ranking),
    )


def execute_profit_validation_search(
    store: ValidationResultStore,
    *,
    brand: str,
    category: str,
    market_mode: str = "FIXTURE",
    runner: MultiBrandDiscoveryRunner | None = None,
    config: ValidationConfig | None = None,
) -> ValidationPipelineResult:
    """Execute profit validation search and persist the latest snapshot."""
    pipeline_result = run_profit_validation_search(
        brand=brand,
        category=category,
        market_mode=market_mode,
        runner=runner,
        config=config,
    )
    store.save(pipeline_result.snapshot)
    return pipeline_result


def _build_selling_listings_by_id(arbitrage_ranking, *, connector_resolver) -> dict:
    listings_by_id: dict[str, object] = {}
    for item in arbitrage_ranking:
        listing = resolve_selling_listing(
            selling_market=item.selling_market,
            keyword=item.product,
            selling_url=item.selling_url,
            connector_resolver=connector_resolver,
        )
        if listing is not None:
            listings_by_id[item.external_id] = listing
    return listings_by_id
