"""The RealReal public search page acquisition and parsing."""

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

REALREAL_SEARCH_URL = "https://www.therealreal.com/products?keywords={query}"
REALREAL_BASE_URL = "https://www.therealreal.com"
SOURCE_NAME = "The RealReal"
DEFAULT_PURCHASE_LIMIT = 20

PRODUCT_HREF_PATTERN = re.compile(r"/products/[^?#]+", re.IGNORECASE)
PLP_TESTID_PATTERN = re.compile(r"^plp-product/(\d+)$", re.IGNORECASE)
CONDITION_PATTERN = re.compile(
    r"\b(Pristine|Excellent|Very Good|Good|Fair|Poor)\b",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")

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


def parse_realreal_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = SOURCE_NAME,
) -> list[AcquiredListing]:
    """Parse The RealReal search HTML into acquisition listings.

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
    """Convert one acquired The RealReal listing to connector MarketListing."""
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


class RealRealAcquirer:
    """Acquire overseas purchase listings from public The RealReal search pages."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = REALREAL_SEARCH_URL,
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
        """Search The RealReal by keyword and return listings with product URLs."""
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
                wait_selector="[data-testid^='plp-product/'], a[href*='/products/']",
            )
            html = fetch.html
            listings = parse_realreal_html(html)[:cap]
            if fetch.blocked_reason and not listings:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            if _is_hard_captcha_challenge(html) and not listings:
                raise AcquisitionBlockedError(BlockingReason.CAPTCHA_REQUIRED, fetch.url)
        else:
            listings = parse_realreal_html(html)[:cap]

        if not listings:
            if _is_hard_captcha_challenge(html):
                return AcquisitionResult(
                    status=AcquisitionStatus.BLOCKED,
                    blocking_reason=BlockingReason.CAPTCHA_REQUIRED.value,
                    detail="The RealReal CAPTCHA/blocked page with no product listings",
                    search_query=query,
                    source=SOURCE_NAME,
                )
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No The RealReal product listings found",
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
    for node in soup.select("[data-testid^='plp-product/']"):
        testid = node.get("data-testid") or ""
        if not PLP_TESTID_PATTERN.match(testid):
            continue
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
    title = _clean_title(text, url=url)
    if not title:
        title = _clean_title(link.get("title") or link.get_text(" ", strip=True), url=url)
    if not title:
        return None

    price, currency = _parse_price_text(text)
    if price is None or price <= 0:
        return None

    testid = node.get("data-testid") or ""
    match = PLP_TESTID_PATTERN.match(testid)
    external_id = match.group(1) if match else _external_id_from_url(url)
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
        if not url or url.rstrip("/").count("/") < 4:
            continue
        parent = link.find_parent(["div", "li", "article"])
        text = " ".join((parent or link).get_text(" ", strip=True).split())
        title = _clean_title(text, url=url) or _clean_title(link.get("title") or "", url=url)
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
        return value.split("?")[0].split("#")[0]
    return f"{REALREAL_BASE_URL}{path}"


def _external_id_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slug or url


def _parse_price_text(text: str) -> tuple[Decimal | None, str]:
    """Prefer the current sale price (last $ amount) over a crossed-out Was price."""
    matches = PRICE_PATTERN.findall(text or "")
    if not matches:
        return None, "USD"
    raw = matches[-1].replace(",", "")
    try:
        return Decimal(raw), "USD"
    except InvalidOperation:
        return None, "USD"


def _extract_condition(text: str) -> str:
    match = CONDITION_PATTERN.search(text or "")
    if not match:
        return ""
    return match.group(1).title()


def _clean_title(text: str, *, url: str = "") -> str:
    cleaned = text or ""
    cleaned = re.sub(r"Was:\s*\$[\d,]+(?:\.\d+)?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Now\s+\d+%\s+off", " ", cleaned, flags=re.IGNORECASE)
    cleaned = PRICE_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\b\d+\s*$", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|")
    if cleaned:
        return cleaned
    # Fallback: derive readable title from URL slug
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"-[a-z0-9]{4,6}$", "", slug)
    return slug.replace("-", " ").strip().title()


def _infer_brand(title: str) -> str:
    lowered = title.lower()
    for marker, brand in BRAND_MARKERS:
        if marker in lowered:
            return brand
    return ""


def _infer_category(title: str, url: str = "") -> str:
    combined = f"{title} {url}".lower()
    if any(token in combined for token in ("wallet", "card case", "card holder", "key holder", "coin purse")):
        return "Wallet"
    if "backpack" in combined:
        return "Backpack"
    if any(token in combined for token in ("tote", "neverfull")):
        return "Tote Bag"
    if any(token in combined for token in ("shoulder", "flap", "kelly", "birkin", "handbag", "bag", "handbags")):
        return "Bag"
    if "/accessories/" in combined:
        return "Accessory"
    return "Bag"


def _is_hard_captcha_challenge(html: str) -> bool:
    lowered = (html or "").lower()
    if "verify you are human" in lowered or "are you a robot" in lowered:
        return True
    if "captcha challenge" in lowered or "g-recaptcha-response" in lowered:
        return True
    if "captcha" in lowered and "plp-product/" not in lowered and "/products/" not in lowered:
        return True
    return False
