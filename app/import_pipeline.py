"""Import pipeline for CSV/manual market listings."""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.connectors.models import MarketListing
from marketplace.importers.connector import ImportedMarketConnector
from marketplace.importers.converters import market_listing_to_supplier_product
from marketplace.importers.supplier_adapter import ImportedProductSupplierClient
from profit_discovery.arbitrage import create_arbitrage_ranking
from profit_discovery.arbitrage.resolver import ArbitrageOpportunityResolver
from profit_discovery.cli.discovery_command import (
    build_default_market_aggregator,
    build_domestic_market_runtime_config,
)
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.discovery_runner.runner import DiscoveryRunner
from profit_discovery.market_connector.connector import SupplierMarketConnector
from profit_discovery.opportunity.identity_pipeline import build_identity_demand_integrated_ranking
from profit_discovery.profit_ranking import rank_used_luxury_products
from profit_discovery.arbitrage.sources import normalize_purchase_source
from marketplace.connectors.resolver import MarketConnectorResolver

from app.storage.market_listing_converters import market_listing_record_from_listing
from app.storage.market_listing_repository import MarketListingRepository
from app.store import DashboardResultStore, DashboardSearchSnapshot


@dataclass(frozen=True, slots=True)
class ImportPipelineResult:
    """Output from one import-driven dashboard run."""

    snapshot: DashboardSearchSnapshot
    imported_count: int
    ranked_count: int
    skipped_count: int = 0
    errors: tuple[str, ...] = ()


def run_import_dashboard_pipeline(
    listings: list[MarketListing],
    *,
    listing_repository: MarketListingRepository | None = None,
    live_market: bool = False,
) -> ImportPipelineResult:
    """Evaluate imported listings and build an arbitrage dashboard snapshot."""
    used_luxury_config = UsedLuxuryModeConfig.default()
    allowed_brands = {brand.lower() for brand in used_luxury_config.all_brand_names()}
    eligible_listings = [
        listing for listing in listings if listing.brand.strip().lower() in allowed_brands
    ]
    skipped_count = len(listings) - len(eligible_listings)

    repository = listing_repository or MarketListingRepository()
    for listing in eligible_listings:
        repository.save(market_listing_record_from_listing(listing))

    supplier_products = [market_listing_to_supplier_product(listing) for listing in eligible_listings]
    if not supplier_products:
        snapshot = DashboardSearchSnapshot(
            brand="Import",
            category="Mixed",
            market_mode="IMPORT",
            arbitrage_ranking=[],
            profit_ranking=[],
            candidates_by_id={},
            listings_by_id={},
        )
        return ImportPipelineResult(
            snapshot=snapshot,
            imported_count=len(listings),
            ranked_count=0,
            skipped_count=skipped_count,
        )

    market_config = build_domestic_market_runtime_config(live_market=live_market)
    aggregator, _market_resolution = build_default_market_aggregator(
        market_config,
        used_luxury=True,
    )
    supplier_client = ImportedProductSupplierClient(supplier_products)
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_aggregator=aggregator,
        ),
    )
    batch_result = discovery_runner.evaluate_products(supplier_products)
    successful_candidates = [
        candidate
        for candidate in batch_result.results
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    demand_opportunities = build_identity_demand_integrated_ranking(successful_candidates)

    connectors_by_market = _build_import_connectors(eligible_listings)
    connector_resolver = MarketConnectorResolver()
    arbitrage_ranking = create_arbitrage_ranking(
        demand_opportunities,
        config=used_luxury_config,
        resolver=ArbitrageOpportunityResolver(
            config=used_luxury_config,
            market_connector_resolver=_InjectedImportConnectorResolver(
                base_resolver=connector_resolver,
                connectors_by_market=connectors_by_market,
            ),
        ),
    )
    profit_ranking = rank_used_luxury_products(
        demand_opportunities,
        config=used_luxury_config,
    )
    candidates_by_id = {
        candidate.supplier_product.external_id: candidate
        for candidate in successful_candidates
    }
    listings_by_id = {
        listing.id: listing
        for listing in eligible_listings
    }
    snapshot = DashboardSearchSnapshot(
        brand="Import",
        category="Mixed",
        market_mode="IMPORT",
        arbitrage_ranking=arbitrage_ranking,
        profit_ranking=profit_ranking,
        candidates_by_id=candidates_by_id,
        listings_by_id=listings_by_id,
    )
    return ImportPipelineResult(
        snapshot=snapshot,
        imported_count=len(listings),
        ranked_count=len(arbitrage_ranking),
        skipped_count=skipped_count,
    )


def execute_import_dashboard_pipeline(
    store: DashboardResultStore,
    listings: list[MarketListing],
    *,
    listing_repository: MarketListingRepository | None = None,
    live_market: bool = False,
) -> ImportPipelineResult:
    """Run import pipeline and persist dashboard snapshot."""
    result = run_import_dashboard_pipeline(
        listings,
        listing_repository=listing_repository,
        live_market=live_market,
    )
    store.save(result.snapshot)
    return result


def _build_import_connectors(listings: list[MarketListing]) -> dict[str, ImportedMarketConnector]:
    grouped: dict[str, list[MarketListing]] = {}
    for listing in listings:
        market_name = normalize_purchase_source(listing.market_name)
        grouped.setdefault(market_name, []).append(listing)
    return {
        market_name: ImportedMarketConnector(market_name=market_name, listings=market_listings)
        for market_name, market_listings in grouped.items()
    }


class _InjectedImportConnectorResolver:
    """Resolve imported listings through pre-built import connectors."""

    def __init__(
        self,
        *,
        base_resolver: MarketConnectorResolver,
        connectors_by_market: dict[str, ImportedMarketConnector],
    ) -> None:
        self._base_resolver = base_resolver
        self._connectors_by_market = connectors_by_market

    def resolve_purchase_connector(self, purchase_source: str, *, injected_connector=None):
        connector = self._connectors_by_market.get(purchase_source)
        if connector is not None:
            return self._base_resolver.resolve(
                purchase_source,
                injected_connector=connector,
            )
        return self._base_resolver.resolve_purchase_connector(
            purchase_source,
            injected_connector=injected_connector,
        )

    def resolve_selling_connector(self, selling_market: str, *, injected_connector=None):
        return self._base_resolver.resolve_selling_connector(
            selling_market,
            injected_connector=injected_connector,
        )
