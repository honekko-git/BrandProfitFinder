"""Fashionphile public search page acquisition and parsing."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionResult, AcquisitionStatus
from marketplace.connectors.models import MarketListing

FASHIONPHILE_SEARCH_URL = "https://www.fashionphile.com/search?q={query}"
DEFAULT_PURCHASE_LIMIT = 10


def parse_fashionphile_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = "Fashionphile",
) -> list[AcquiredListing]:
    """Parse Fashionphile search HTML using multiple selector strategies."""
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    listings: list[AcquiredListing] = []
    seen: set[str] = set()

    for listing in _parse_json_ld_products(html, timestamp, source):
        if listing.external_id not in seen:
            seen.add(listing.external_id)
            listings.append(listing)

    for listing in _parse_product_cards(html, timestamp, source):
        if listing.external_id not in seen:
            seen.add(listing.external_id)
            listings.append(listing)

    for listing in _parse_anchor_products(html, timestamp, source):
        if listing.external_id not in seen:
            seen.add(listing.external_id)
            listings.append(listing)

    return listings


def acquired_listing_to_market_listing(listing: AcquiredListing) -> MarketListing:
    """Convert one acquired listing to connector MarketListing."""
    return MarketListing(
        id=listing.external_id,
        title=listing.title,
        brand=listing.brand,
        category=listing.category,
        condition=listing.condition,
        price=listing.price,
        currency=listing.currency,
        market_name=listing.source,
        url=listing.url,
        source_type="LIVE",
        created_at=datetime.fromisoformat(listing.retrieved_at),
    )


class FashionphileAcquirer:
    """Acquire Chanel wallet listings from Fashionphile public search."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = FASHIONPHILE_SEARCH_URL,
        purchase_limit: int = DEFAULT_PURCHASE_LIMIT,
    ) -> None:
        self._browser = browser or BrowserSession()
        self._search_url_template = search_url_template
        self._purchase_limit = purchase_limit

    def acquire(
        self,
        *,
        brand: str = "Chanel",
        category: str = "Wallet",
        html: str | None = None,
        search_url: str | None = None,
    ) -> AcquisitionResult:
        """Acquire purchase listings from one public search page."""
        query = f"{brand} {category}".strip()
        url = search_url or self._search_url_template.format(query=quote_plus(query))

        if html is None:
            fetch = self._browser.fetch_html(url)
            if fetch.blocked_reason:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            html = fetch.html

        listings = parse_fashionphile_html(html)[: self._purchase_limit]
        filtered = [
            listing
            for listing in listings
            if brand.lower() in listing.brand.lower() or brand.lower() in listing.title.lower()
        ]
        if not filtered:
            filtered = [
                listing
                for listing in listings
                if _looks_like_wallet(listing.title, listing.category)
            ]

        if not listings:
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No Fashionphile product cards found",
                search_query=query,
                source="Fashionphile",
            )
        if not filtered:
            return AcquisitionResult(
                status=AcquisitionStatus.PARTIAL,
                listings=tuple(listings[: self._purchase_limit]),
                detail="Results found but brand/category filter matched none",
                search_query=query,
                source="Fashionphile",
            )

        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            listings=tuple(filtered[: self._purchase_limit]),
            search_query=query,
            source="Fashionphile",
        )

    def search_keyword(
        self,
        keyword: str,
        *,
        html: str | None = None,
        search_url: str | None = None,
        limit: int | None = None,
    ) -> AcquisitionResult:
        """Search Fashionphile by free-text keyword (raw listings, no AI)."""
        query = str(keyword or "").strip()
        if not query:
            return AcquisitionResult(
                status=AcquisitionStatus.FAILED,
                detail="keyword is required",
                search_query="",
                source="Fashionphile",
            )
        cap = max(1, int(limit if limit is not None else self._purchase_limit))
        url = search_url or self._search_url_template.format(query=quote_plus(query))

        if html is None:
            fetch = self._browser.fetch_html(url)
            if fetch.blocked_reason:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            html = fetch.html

        listings = parse_fashionphile_html(html)[:cap]
        if not listings:
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No Fashionphile product cards found",
                search_query=query,
                source="Fashionphile",
            )
        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            listings=tuple(listings),
            search_query=query,
            source="Fashionphile",
        )


def _parse_json_ld_products(html: str, retrieved_at: str, source: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in {"Product", "ItemList"}:
                continue
            if item.get("@type") == "ItemList":
                for element in item.get("itemListElement", []):
                    product = element.get("item") if isinstance(element, dict) else None
                    if isinstance(product, dict):
                        listing = _listing_from_json_ld(product, retrieved_at, source)
                        if listing is not None:
                            listings.append(listing)
            else:
                listing = _listing_from_json_ld(item, retrieved_at, source)
                if listing is not None:
                    listings.append(listing)
    return listings


def _listing_from_json_ld(item: dict, retrieved_at: str, source: str) -> AcquiredListing | None:
    title = str(item.get("name", "")).strip()
    url = str(item.get("url", "")).strip()
    if not title or not url:
        return None
    price, currency = _extract_offer_price(item.get("offers", {}))
    if price is None:
        return None
    external_id = _external_id_from_url(url)
    brand = str(item.get("brand", {}).get("name", "") if isinstance(item.get("brand"), dict) else item.get("brand", ""))
    return AcquiredListing(
        external_id=external_id,
        title=title,
        brand=brand or _infer_brand(title),
        category=_infer_category(title),
        condition=str(item.get("itemCondition", "Used")),
        price=price,
        currency=currency,
        url=url,
        image_url=str(item.get("image", "")),
        retrieved_at=retrieved_at,
        source=source,
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _parse_product_cards(html: str, retrieved_at: str, source: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    selectors = (
        "[data-product-id]",
        "[data-testid='product-card']",
        ".product-card",
        ".product-tile",
        "article[data-product-id]",
    )
    for selector in selectors:
        for node in soup.select(selector):
            listing = _listing_from_card(node, retrieved_at, source)
            if listing is not None:
                listings.append(listing)
        if listings:
            break
    return listings


def _listing_from_card(node, retrieved_at: str, source: str) -> AcquiredListing | None:
    product_id = (
        node.get("data-product-id")
        or node.get("data-item-id")
        or node.get("id")
        or ""
    )
    link = node.select_one("a[href]")
    title_node = node.select_one("[data-testid='product-title'], .product-title, .title, h2, h3")
    price_node = node.select_one("[data-testid='product-price'], .price, .product-price, [data-price]")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    if not title and link is not None:
        title = link.get_text(" ", strip=True)
    url = ""
    if link is not None:
        url = link.get("href", "").strip()
        if url.startswith("/"):
            url = f"https://www.fashionphile.com{url}"
    if not title or not url:
        return None

    price_text = price_node.get_text(" ", strip=True) if price_node else node.get("data-price", "")
    price, currency = _parse_price_text(price_text)
    if price is None:
        return None

    external_id = str(product_id or _external_id_from_url(url))
    condition_node = node.select_one(".condition, [data-condition]")
    condition = condition_node.get_text(" ", strip=True) if condition_node else "Used"
    return AcquiredListing(
        external_id=external_id,
        title=title,
        brand=_infer_brand(title),
        category=_infer_category(title),
        condition=condition or "Used",
        price=price,
        currency=currency,
        url=url,
        retrieved_at=retrieved_at,
        source=source,
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _parse_anchor_products(html: str, retrieved_at: str, source: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    for link in soup.select("a[href*='/products/'], a[href*='/p/'], a[href*='/shop/']"):
        title = link.get_text(" ", strip=True)
        url = link.get("href", "").strip()
        if not title or not url:
            continue
        if url.startswith("/"):
            url = f"https://www.fashionphile.com{url}"
        parent = link.find_parent(["article", "li", "div"])
        price_text = parent.get_text(" ", strip=True) if parent is not None else title
        price, currency = _parse_price_text(price_text)
        if price is None:
            continue
        listings.append(
            AcquiredListing(
                external_id=_external_id_from_url(url),
                title=title,
                brand=_infer_brand(title),
                category=_infer_category(title),
                condition="Used",
                price=price,
                currency=currency,
                url=url,
                retrieved_at=retrieved_at,
                source=source,
                raw_title=title,
                acquisition_status=AcquisitionStatus.LIVE,
            )
        )
    return listings


def _extract_offer_price(offers: object) -> tuple[Decimal | None, str]:
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None, "USD"
    raw_price = offers.get("price")
    currency = str(offers.get("priceCurrency", "USD"))
    if raw_price is None:
        return None, currency
    try:
        return Decimal(str(raw_price)), currency
    except InvalidOperation:
        return None, currency


def _parse_price_text(text: str) -> tuple[Decimal | None, str]:
    normalized = text.replace(",", "")
    usd_match = re.search(r"\$\s*([\d]+(?:\.\d+)?)", normalized)
    if usd_match:
        return Decimal(usd_match.group(1)), "USD"
    jpy_match = re.search(r"([\d]+)\s*円|¥\s*([\d]+)", normalized)
    if jpy_match:
        amount = jpy_match.group(1) or jpy_match.group(2)
        return Decimal(amount), "JPY"
    return None, "USD"


def _external_id_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slug or url


def _infer_brand(title: str) -> str:
    lowered = title.lower()
    if "chanel" in lowered:
        return "Chanel"
    if "louis vuitton" in lowered or "lv" in lowered.split():
        return "Louis Vuitton"
    return ""


def _infer_category(title: str) -> str:
    lowered = title.lower()
    if "wallet" in lowered or "coin purse" in lowered or "card holder" in lowered:
        return "Wallet"
    return "bag"


def _looks_like_wallet(title: str, category: str) -> bool:
    combined = f"{title} {category}".lower()
    return "wallet" in combined or "coin purse" in combined or "card holder" in combined
