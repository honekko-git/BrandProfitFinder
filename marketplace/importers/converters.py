"""Converters between imported listings and discovery pipeline inputs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from marketplace.connectors.models import MarketListing
from marketplace.importers.validators import normalize_row
from profit_discovery.arbitrage.sources import normalize_purchase_source
from supplier.models import SupplierProduct, SupplierType


def market_listing_to_supplier_product(listing: MarketListing) -> SupplierProduct:
    """Convert one imported MarketListing into a SupplierProduct."""
    purchase_price = float(listing.price)
    if listing.currency.upper() != "JPY":
        purchase_price = float(listing.price)
    condition = listing.condition.strip()
    normalized_condition = condition.upper()
    if normalized_condition not in {SupplierType.USED.value, "PREOWNED", "PRE-OWNED"}:
        condition = SupplierType.USED.value
    return SupplierProduct(
        supplier_name=normalize_purchase_source(listing.market_name),
        external_id=listing.id,
        title=listing.title,
        brand=listing.brand,
        category=listing.category,
        condition=condition,
        purchase_price=purchase_price,
        currency=listing.currency.upper(),
        url=listing.url,
        image_urls=[],
        availability="IN_STOCK",
        metadata={"import_source": listing.source_type},
    )


def market_listing_record_to_market_listing(record) -> MarketListing:
    """Convert one persisted MarketListingRecord into a MarketListing."""
    return MarketListing(
        id=record.external_key,
        title=record.title,
        brand=record.brand,
        category=record.category,
        condition=record.condition,
        price=Decimal(str(record.price)),
        currency=record.currency,
        market_name=record.market_name,
        url=record.url,
        source_type="IMPORT",
        created_at=record.created_at,
    )


def market_listing_to_record_fields(listing: MarketListing) -> dict[str, object]:
    """Extract SQLite-ready fields from one MarketListing."""
    return {
        "title": listing.title,
        "brand": listing.brand,
        "category": listing.category,
        "condition": listing.condition,
        "price": float(listing.price),
        "currency": listing.currency,
        "market_name": listing.market_name,
        "url": listing.url,
        "external_key": listing.id,
    }


def csv_row_to_dict(row: dict[str, str]) -> dict[str, str]:
    """Normalize one CSV/manual row for validation."""
    return normalize_row(row)
