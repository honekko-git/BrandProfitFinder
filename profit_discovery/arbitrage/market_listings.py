"""Helpers for enriching arbitrage opportunities with market connector listings."""

from __future__ import annotations

from profit_discovery.arbitrage.sources import normalize_purchase_source, normalize_selling_market
from marketplace.connectors.base import MarketConnector
from marketplace.connectors.models import MarketListing
from marketplace.connectors.resolver import MarketConnectorResolver
from marketplace.connectors.execution import MarketConnectorExecutionResult
from supplier.models import SupplierProduct


def resolve_purchase_listing(
    product: SupplierProduct,
    *,
    connector_resolver: MarketConnectorResolver | None = None,
    injected_connector: MarketConnector | None = None,
    execution_sink: dict[str, MarketConnectorExecutionResult] | None = None,
) -> MarketListing | None:
    """Resolve one purchase-side MarketListing for a supplier product."""
    purchase_source = normalize_purchase_source(product.supplier_name)
    resolver = connector_resolver or MarketConnectorResolver()
    resolution = resolver.resolve_purchase_connector(
        purchase_source,
        injected_connector=injected_connector,
    )
    connector = resolution.connector
    if connector is None:
        return None

    if product.url.strip():
        listing = connector.get_product(product.url)
        if listing is not None:
            _record_execution(
                execution_sink,
                purchase_source,
                connector,
                resolution.execution,
            )
            return listing

    query = " ".join(part for part in (product.brand, product.category, product.title) if part).strip()
    matches = connector.search_products(query)
    if not matches:
        matches = connector.search_products(product.brand)
    for listing in matches:
        if listing.id == product.external_id:
            _record_execution(
                execution_sink,
                purchase_source,
                connector,
                resolution.execution,
            )
            return listing
    result = matches[0] if matches else None
    _record_execution(execution_sink, purchase_source, connector, resolution.execution)
    return result


def _record_execution(
    execution_sink: dict[str, MarketConnectorExecutionResult] | None,
    market_name: str,
    connector: MarketConnector,
    fallback_execution: MarketConnectorExecutionResult | None,
) -> None:
    if execution_sink is None:
        return
    from marketplace.connectors.live.base import FallbackMarketConnector

    if isinstance(connector, FallbackMarketConnector):
        execution_sink[market_name] = connector.execution
    elif fallback_execution is not None:
        execution_sink[market_name] = fallback_execution


def resolve_selling_listing(
    *,
    selling_market: str,
    keyword: str,
    selling_url: str = "",
    connector_resolver: MarketConnectorResolver | None = None,
    injected_connector: MarketConnector | None = None,
) -> MarketListing | None:
    """Resolve one domestic selling-side MarketListing."""
    market_name = normalize_selling_market(selling_market)
    resolver = connector_resolver or MarketConnectorResolver()
    resolution = resolver.resolve_selling_connector(
        market_name,
        injected_connector=injected_connector,
    )
    connector = resolution.connector
    if connector is None:
        return None

    if selling_url.strip():
        listing = connector.get_product(selling_url)
        if listing is not None:
            return listing

    matches = connector.search_products(keyword)
    return matches[0] if matches else None


def enrich_listing_metadata(
    *,
    purchase_listing: MarketListing | None,
    selling_listing: MarketListing | None,
    fallback_market_source: str,
    fallback_condition: str,
    fallback_listing_url: str,
) -> tuple[str, str, str]:
    """Choose display metadata from connector listings with safe fallbacks."""
    listing = purchase_listing or selling_listing
    market_source = (
        purchase_listing.market_name
        if purchase_listing is not None
        else selling_listing.market_name
        if selling_listing is not None
        else fallback_market_source
    )
    condition = listing.condition if listing is not None else fallback_condition
    listing_url = (
        purchase_listing.url
        if purchase_listing is not None
        else selling_listing.url
        if selling_listing is not None
        else fallback_listing_url
    )
    return market_source, condition, listing_url
