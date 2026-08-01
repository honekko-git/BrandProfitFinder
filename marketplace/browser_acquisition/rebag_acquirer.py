"""Rebag public search page acquisition and parsing."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionResult, AcquisitionStatus
from marketplace.connectors.models import MarketListing

REBAG_SEARCH_URL = "https://www.rebag.com/shop/?search={query}"
REBAG_BASE_URL = "https://www.rebag.com"
SOURCE_NAME = "Rebag"
DEFAULT_PURCHASE_LIMIT = 20

PRODUCT_HREF_PATTERN = re.compile(r"/products/[^?#]+", re.IGNORECASE)
CONDITION_PATTERN = re.compile(
    r"\b(Pristine|Excellent|Very Good|Good|Fair|Poor)\s+Condition\b",
    re.IGNORECASE,
)
HARDWARE_PATTERN = re.compile(r"\b(Gold|Silver|Palladium|Ruthenium|Rose Gold)\s+Hardware\b", re.IGNORECASE)

BRAND_MARKERS = (
    ("louis vuitton", "Louis Vuitton"),
    ("hermes", "Hermes"),
    ("hermès", "Hermes"),
    ("chanel", "Chanel"),
    ("gucci", "Gucci"),
    ("prada", "Prada"),
    ("dior", "Dior"),
    ("saint laurent", "Saint Laurent"),
    ("ysl", "Saint Laurent"),
    ("bottega veneta", "Bottega Veneta"),
    ("fendi", "Fendi"),
    ("celine", "Celine"),
    ("balenciaga", "Balenciaga"),
    ("tiffany", "Tiffany"),
    ("cartier", "Cartier"),
    ("loewe", "Loewe"),
)


def parse_rebag_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = SOURCE_NAME,
) -> list[AcquiredListing]:
    """Parse Rebag search HTML into acquisition listings.

    Listings without an individual product URL or valid USD price are skipped.
    """
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    listings: list[AcquiredListing] = []
    seen: set[str] = set()
    for listing in _parse_product_cards(html, timestamp, source):
        key = listing.url or listing.external_id
        if not key or key in seen:
            continue
        seen.add(key)
        listings.append(listing)
    if listings:
        return listings
    for listing in _parse_product_anchors(html, timestamp, source):
        key = listing.url or listing.external_id
        if not key or key in seen:
            continue
        seen.add(key)
        listings.append(listing)
    return listings


def acquired_listing_to_market_listing(listing: AcquiredListing) -> MarketListing:
    """Convert one acquired Rebag listing to connector MarketListing."""
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


class RebagAcquirer:
    """Acquire overseas purchase listings from public Rebag search pages."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = REBAG_SEARCH_URL,
        purchase_limit: int = DEFAULT_PURCHASE_LIMIT,
    ) -> None:
        self._browser = browser or BrowserSession()
        self._search_url_template = search_url_template
        self._purchase_limit = purchase_limit

    def search_keyword(
        self,
        keyword: str,
        *,
        html: str | None = None,
        search_url: str | None = None,
        limit: int | None = None,
    ) -> AcquisitionResult:
        """Search Rebag by keyword and return listings with mandatory product URLs."""
        query = str(keyword or "").strip()
        if not query:
            return AcquisitionResult(
                status=AcquisitionStatus.FAILED,
                detail="keyword is required",
                search_query="",
                source=SOURCE_NAME,
            )
        cap = max(1, int(limit if limit is not None else self._purchase_limit))
        url = search_url or self._search_url_template.format(query=quote_plus(query))

        if html is None:
            fetch = self._browser.fetch_html(
                url,
                wait_selector="div.plp__product[data-product-id], a[href*='/products/']",
            )
            html = fetch.html
            # Soft captcha badges alone are not a hard block when products parse.
            listings = parse_rebag_html(html)[:cap]
            if fetch.blocked_reason and not listings:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            if _is_hard_captcha_challenge(html) and not listings:
                raise AcquisitionBlockedError(BlockingReason.CAPTCHA_REQUIRED, fetch.url)
        else:
            listings = parse_rebag_html(html)[:cap]

        if not listings:
            if _is_hard_captcha_challenge(html):
                return AcquisitionResult(
                    status=AcquisitionStatus.BLOCKED,
                    blocking_reason=BlockingReason.CAPTCHA_REQUIRED.value,
                    detail="Rebag CAPTCHA/blocked page with no product listings",
                    search_query=query,
                    source=SOURCE_NAME,
                )
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No Rebag product listings found",
                search_query=query,
                source=SOURCE_NAME,
            )
        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            listings=tuple(listings),
            search_query=query,
            source=SOURCE_NAME,
        )


def _parse_product_cards(html: str, retrieved_at: str, source: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    for node in soup.select("div.plp__product[data-product-id], div.plp-product[data-product-id], [data-product-id]"):
        listing = _listing_from_card(node, retrieved_at, source)
        if listing is not None:
            listings.append(listing)
    return listings


def _listing_from_card(node, retrieved_at: str, source: str) -> AcquiredListing | None:
    link = node.select_one("a[href*='/products/']")
    if link is None:
        return None
    url = _absolute_product_url(link.get("href") or "")
    if not url:
        return None

    text = " ".join(node.get_text(" ", strip=True).split())
    title = _clean_title(text)
    if not title:
        title = _clean_title(link.get_text(" ", strip=True))
    if not title:
        return None

    price, currency = _parse_price_text(text)
    if price is None:
        price_node = node.select_one(".price, .product-price, [data-price], .money")
        if price_node is not None:
            price, currency = _parse_price_text(price_node.get_text(" ", strip=True))
    if price is None or price <= 0:
        return None

    product_id = str(node.get("data-product-id") or "").strip()
    external_id = product_id or _external_id_from_url(url)
    image = node.select_one("img[src]")
    image_url = (image.get("src") if image is not None else "") or ""
    condition = _extract_condition(text) or "Used"
    return AcquiredListing(
        external_id=external_id,
        title=title,
        brand=_infer_brand(title),
        category=_infer_category(title, url),
        condition=condition,
        price=price,
        currency=currency,
        url=url,
        image_url=image_url,
        retrieved_at=retrieved_at,
        source=source,
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _parse_product_anchors(html: str, retrieved_at: str, source: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    for link in soup.select("a[href*='/products/']"):
        url = _absolute_product_url(link.get("href") or "")
        if not url:
            continue
        parent = link.find_parent(["div", "li", "article"])
        text = " ".join((parent or link).get_text(" ", strip=True).split())
        title = _clean_title(text) or _clean_title(link.get_text(" ", strip=True))
        if not title:
            continue
        price, currency = _parse_price_text(text)
        if price is None or price <= 0:
            continue
        listings.append(
            AcquiredListing(
                external_id=_external_id_from_url(url),
                title=title,
                brand=_infer_brand(title),
                category=_infer_category(title, url),
                condition=_extract_condition(text) or "Used",
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


def _absolute_product_url(href: str) -> str:
    value = (href or "").strip()
    if not value:
        return ""
    match = PRODUCT_HREF_PATTERN.search(value)
    if not match:
        return ""
    path = match.group(0)
    if value.startswith("http"):
        # Keep host from absolute URL when already full.
        if "/products/" in value:
            return value.split("?")[0].split("#")[0]
        return f"{REBAG_BASE_URL}{path}"
    return f"{REBAG_BASE_URL}{path}"


def _external_id_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slug or url


def _parse_price_text(text: str) -> tuple[Decimal | None, str]:
    normalized = (text or "").replace(",", "")
    match = re.search(r"\$\s*([\d]+(?:\.\d+)?)", normalized)
    if not match:
        return None, "USD"
    try:
        return Decimal(match.group(1)), "USD"
    except InvalidOperation:
        return None, "USD"


def _extract_condition(text: str) -> str:
    match = CONDITION_PATTERN.search(text or "")
    if not match:
        return ""
    return f"{match.group(1).title()} Condition"


def _clean_title(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"^\s*(Investment Piece|New Arrival|Sale)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*\d+\s+", "", cleaned)
    cleaned = CONDITION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\$\s*[\d,]+(?:\.\d+)?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|")
    return cleaned


def _infer_brand(title: str) -> str:
    lowered = title.lower()
    for marker, brand in BRAND_MARKERS:
        if marker in lowered:
            return brand
    return ""


def _infer_category(title: str, url: str = "") -> str:
    combined = f"{title} {url}".lower()
    if any(token in combined for token in ("wallet", "card case", "card holder", "coin purse")):
        return "Wallet"
    if "backpack" in combined:
        return "Backpack"
    if any(token in combined for token in ("tote", "neverfull")):
        return "Tote Bag"
    if any(token in combined for token in ("shoulder", "flap", "kelly", "birkin", "handbag", "bag")):
        return "Bag"
    if "/products/handbags" in combined:
        return "Bag"
    if "/products/accessories" in combined or "belt" in combined:
        return "Accessory"
    return "Bag"


def _is_hard_captcha_challenge(html: str) -> bool:
    lowered = (html or "").lower()
    if "verify you are human" in lowered or "are you a robot" in lowered:
        return True
    if "captcha challenge" in lowered or "g-recaptcha-response" in lowered:
        return True
    # Badge CSS alone is not a challenge page.
    if "captcha" in lowered and "grecaptcha-badge" not in lowered and "plp__product" not in lowered:
        return True
    return False
