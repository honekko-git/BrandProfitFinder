"""Market source definitions for used luxury arbitrage."""

from __future__ import annotations

OVERSEAS_PURCHASE_SOURCES: tuple[str, ...] = (
    "Fashionphile",
    "The RealReal",
    "Vestiaire Collective",
)

DOMESTIC_SELLING_MARKETS: tuple[str, ...] = (
    "Mercari",
    "Yahoo Auction",
)

OVERSEAS_SOURCE_ALIASES: dict[str, str] = {
    "fashionphile": "Fashionphile",
    "the realreal": "The RealReal",
    "therealreal": "The RealReal",
    "vestiaire": "Vestiaire Collective",
    "vestiaire collective": "Vestiaire Collective",
}

DOMESTIC_MARKET_ALIASES: dict[str, str] = {
    "mercari": "Mercari",
    "yahoo_auction": "Yahoo Auction",
    "yahoo auction": "Yahoo Auction",
    "yahoo": "Yahoo Auction",
}


def normalize_purchase_source(raw_source: str) -> str:
    """Map a supplier identifier to a display purchase source name."""
    normalized = raw_source.strip().lower()
    if normalized in OVERSEAS_SOURCE_ALIASES:
        return OVERSEAS_SOURCE_ALIASES[normalized]
    if raw_source.strip() in OVERSEAS_PURCHASE_SOURCES:
        return raw_source.strip()
    return raw_source.strip().title() or "Unknown"


def normalize_selling_market(raw_market: str) -> str:
    """Map a domestic market identifier to a display selling market name."""
    normalized = raw_market.strip().lower().replace(" ", "_")
    if normalized in DOMESTIC_MARKET_ALIASES:
        return DOMESTIC_MARKET_ALIASES[normalized]
    if raw_market.strip() in DOMESTIC_SELLING_MARKETS:
        return raw_market.strip()
    return raw_market.strip().title() or "Unknown"


def build_purchase_url(source: str, product_url: str) -> str:
    """Return the stored purchase URL for one overseas listing."""
    return product_url.strip()


def build_selling_url(market: str, *, keyword: str) -> str:
    """Build a placeholder domestic selling-market URL for later live integration."""
    normalized = market.strip().lower()
    query = keyword.strip().replace(" ", "+")
    if normalized == "mercari":
        return f"https://jp.mercari.com/search?keyword={query}"
    if normalized in {"yahoo auction", "yahoo_auction"}:
        return f"https://auctions.yahoo.co.jp/search/search?p={query}"
    return f"https://example.invalid/{normalized}?q={query}"
