"""
Currency safety helpers for cross-marketplace comparison.

Ensures non-JPY source amounts are never treated as authoritative JPY inputs.
This module validates comparability only; it does not convert currencies.
"""

from __future__ import annotations

from decimal import Decimal

from config.constants import CURRENCY_JPY
from models.marketplace_listing import MarketplaceListing


def normalize_currency_code(value: object | None) -> str | None:
    """
    Normalize a currency code or return None when unknown.

    Blank strings become None. Known codes are uppercased (``jpy`` -> ``JPY``).
    Malformed codes are returned uppercased but are not treated as JPY unless
    they normalize exactly to ``JPY``.
    """
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def resolve_listing_currency(listing: MarketplaceListing | None) -> str | None:
    """
    Resolve listing currency from explicit fields or source metadata.

    Listing ``currency`` takes precedence over ``source_metadata['source_currency']``.
    """
    if listing is None:
        return None
    currency = normalize_currency_code(listing.currency)
    if currency:
        return currency
    meta = listing.source_metadata or {}
    return normalize_currency_code(meta.get("source_currency"))


def is_jpy_comparable_currency(currency: str | None) -> bool:
    """Return True only when currency is explicitly JPY after normalization."""
    return currency == CURRENCY_JPY


def is_jpy_comparable_listing(listing: MarketplaceListing | None) -> bool:
    """Return True when listing currency is explicitly JPY."""
    return is_jpy_comparable_currency(resolve_listing_currency(listing))


def listing_source_price_amount(listing: MarketplaceListing | None) -> Decimal | None:
    """
    Return the source listing price amount without currency conversion.

    The numeric field name ``price_jpy`` is storage-only; currency context must
    be read separately via ``resolve_listing_currency``.
    """
    if listing is None:
        return None
    amount = listing.price_jpy
    if amount is None or amount <= 0:
        return None
    return amount


def authoritative_jpy_sale_price(listing: MarketplaceListing | None) -> Decimal | None:
    """
    Return an authoritative JPY sale price only when currency is explicitly JPY.

    Never treats USD/EUR/GBP numeric amounts as JPY. Does not convert currencies.
    """
    if not is_jpy_comparable_listing(listing):
        return None
    amount = listing_source_price_amount(listing)
    if amount is None:
        return None
    total = listing.total_price_jpy
    if total is not None and total > 0:
        return total
    return listing.compute_total_price_jpy()
