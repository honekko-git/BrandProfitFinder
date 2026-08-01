"""Vestiaire Collective public search page acquisition and parsing.

Observed public structure (2026):
- Search URL: https://www.vestiairecollective.com/search/?q={query}
- Product cards: a[data-cy^='catalog__productCard__'] with href ending in .shtml
- Individual URL example:
  /women-accessories/purses-wallets-cases/chanel/black-leather-chanel-purse-68880598.shtml
- Prices appear in aria-label as "Price: ¥109,100" / "$695" / "€420" / "£310"
- Locale may localize display currency (JPY/USD/EUR/GBP); parse displayed currency, do not assume USD
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionResult, AcquisitionStatus
from marketplace.connectors.models import MarketListing

VESTIAIRE_SEARCH_URL = "https://www.vestiairecollective.com/search/?q={query}"
VESTIAIRE_BASE_URL = "https://www.vestiairecollective.com"
SOURCE_NAME = "Vestiaire Collective"
DEFAULT_PURCHASE_LIMIT = 20

PRODUCT_HREF_PATTERN = re.compile(
    r"^/[a-z0-9\-]+(?:/[a-z0-9\-]+)*/[a-z0-9\-]+/\S+-\d{5,}\.shtml(?:[?#].*)?$",
    re.IGNORECASE,
)
PRODUCT_ID_PATTERN = re.compile(r"-(\d{5,})\.shtml", re.IGNORECASE)
ARIA_PRICE_PATTERN = re.compile(
    r"Price:\s*([€£$¥]|USD|EUR|GBP|JPY)?\s*([\d.,\s]+)\s*([€£$¥]|USD|EUR|GBP|JPY)?",
    re.IGNORECASE,
)
CURRENCY_SYMBOLS = {
    "¥": "JPY",
    "円": "JPY",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}
CONDITION_PATTERN = re.compile(
    r"\b(Never worn|Pristine|Excellent|Very good|Good|Fair|Satisfactory|Correct|Used)\b",
    re.IGNORECASE,
)
SOLD_PATTERN = re.compile(r"\b(sold|reserved|unavailable|withdrawn|out of stock)\b", re.IGNORECASE)

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
    ("céline", "Celine"),
    ("balenciaga", "Balenciaga"),
    ("tiffany", "Tiffany"),
    ("cartier", "Cartier"),
    ("loewe", "Loewe"),
)


def parse_vestiaire_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = SOURCE_NAME,
    base_url: str = VESTIAIRE_BASE_URL,
) -> list[AcquiredListing]:
    """Parse Vestiaire search or product HTML into acquisition listings.

    Listings missing title, active price+currency, or a valid product .shtml URL are skipped.
    """
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    listings: list[AcquiredListing] = []
    seen: set[str] = set()
    for listing in _parse_product_cards(html, timestamp, source, base_url):
        key = listing.url or listing.external_id
        if not key or key in seen:
            continue
        seen.add(key)
        listings.append(listing)
    return listings


def acquired_listing_to_market_listing(listing: AcquiredListing) -> MarketListing:
    """Convert one acquired Vestiaire listing to connector MarketListing."""
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


class VestiaireAcquirer:
    """Acquire overseas purchase listings from public Vestiaire Collective search pages."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = VESTIAIRE_SEARCH_URL,
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
        """Search Vestiaire by keyword and return listings with mandatory product URLs."""
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
                wait_selector="a[data-cy^='catalog__productCard__'], a[href$='.shtml']",
            )
            html = fetch.html
            listings = parse_vestiaire_html(html)[:cap]
            # Soft consent/analytics alone are not a hard block when products parse.
            if fetch.blocked_reason and not listings:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            page_block = _classify_blocking_page(html)
            if page_block and not listings:
                raise AcquisitionBlockedError(page_block, fetch.url)
        else:
            listings = parse_vestiaire_html(html)[:cap]

        if not listings:
            page_block = _classify_blocking_page(html)
            if page_block:
                return AcquisitionResult(
                    status=AcquisitionStatus.BLOCKED,
                    blocking_reason=page_block.value,
                    detail=f"Vestiaire Collective {page_block.value} with no product listings",
                    search_query=query,
                    source=SOURCE_NAME,
                )
            if _looks_malformed(html):
                return AcquisitionResult(
                    status=AcquisitionStatus.FAILED,
                    detail="Vestiaire Collective response malformed or unusable",
                    search_query=query,
                    source=SOURCE_NAME,
                )
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.NO_RESULTS.value,
                detail="No Vestiaire Collective product listings found",
                search_query=query,
                source=SOURCE_NAME,
            )
        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            listings=tuple(listings),
            search_query=query,
            source=SOURCE_NAME,
        )


def _parse_product_cards(html: str, retrieved_at: str, source: str, base_url: str) -> list[AcquiredListing]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[AcquiredListing] = []
    nodes = soup.select("a[data-cy^='catalog__productCard__'], a[class*='productCard__'][href$='.shtml']")
    if not nodes:
        nodes = [
            node
            for node in soup.select("a[href$='.shtml']")
            if PRODUCT_HREF_PATTERN.match((node.get("href") or "").split("?")[0])
        ]
    for node in nodes:
        listing = _listing_from_card(node, retrieved_at, source, base_url)
        if listing is not None:
            listings.append(listing)
    return listings


def _listing_from_card(node, retrieved_at: str, source: str, base_url: str) -> AcquiredListing | None:
    href = node.get("href") or ""
    url = canonicalize_vestiaire_product_url(href, base_url=base_url)
    if not url:
        return None

    aria = " ".join((node.get("aria-label") or "").split())
    text = " ".join(node.get_text(" ", strip=True).split())
    combined = f"{aria} {text}".strip()
    if SOLD_PATTERN.search(combined):
        return None

    title = _title_from_card(aria=aria, text=text, url=url)
    if not title or len(title) < 4:
        return None

    price, currency = _parse_active_price(node, aria=aria, text=text)
    if price is None or price <= 0 or not currency:
        return None

    external_id = _external_id_from_url(url)
    image = node.select_one("img[src]")
    image_url = (image.get("src") if image is not None else "") or ""
    condition = _extract_condition(combined) or "Used"
    return AcquiredListing(
        external_id=external_id,
        title=title,
        brand=_infer_brand(title, url),
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


def canonicalize_vestiaire_product_url(href: str, *, base_url: str = VESTIAIRE_BASE_URL) -> str:
    """Resolve and validate an individual Vestiaire product URL; reject search/category links."""
    raw = str(href or "").strip()
    if not raw:
        return ""
    absolute = urljoin(base_url.rstrip("/") + "/", raw)
    parsed = urlparse(absolute)
    host = (parsed.netloc or "").lower()
    if host and "vestiairecollective.com" not in host:
        return ""
    path = parsed.path or ""
    if not PRODUCT_HREF_PATTERN.match(path):
        return ""
    lower = path.lower()
    if any(token in lower for token in ("/search", "/brands/", "/new-items/", "/journal/", "/my-account")):
        return ""
    # Drop tracking query params; keep path intact (locale/path matter for Vestiaire).
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


def _title_from_card(*, aria: str, text: str, url: str) -> str:
    if aria:
        # aria-label: "Chanel, Leather card wallet, Price: ¥108,000, Ships from United States"
        parts = [part.strip() for part in aria.split(",") if part.strip()]
        brand = parts[0] if parts else ""
        name = ""
        for part in parts[1:]:
            if part.lower().startswith("price:") or part.lower().startswith("ships from"):
                break
            if part.lower().startswith("tagged as"):
                continue
            name = part
            break
        if brand and name:
            title = _clean_title(f"{brand} {name}")
            if title:
                return title
        if name:
            title = _clean_title(name)
            if title:
                return title
    cleaned = _clean_title(text)
    if cleaned:
        return cleaned
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"-\d+\.shtml$", "", slug, flags=re.I)
    return _clean_title(slug.replace("-", " "))


def _clean_title(value: str) -> str:
    text = " ".join(str(value or "").split())
    text = re.sub(r"Price:\s*[€£$¥]?\s*[\d.,\s]+", " ", text, flags=re.I)
    text = re.sub(r"Ships from\s+.+$", " ", text, flags=re.I)
    text = re.sub(r"\bWe love\b", " ", text, flags=re.I)
    text = re.sub(r"[€£$¥]\s*[\d.,]+", " ", text)
    return " ".join(text.split()).strip(" ,-|")


def _parse_active_price(node, *, aria: str, text: str) -> tuple[Decimal | None, str]:
    # Prefer regular/current price nodes over strikethrough/original.
    regular = node.select_one(
        "[class*='regularPrice'], [class*='currentPrice'], [class*='text--price']:not([class*='original'])"
    )
    if regular is not None:
        price, currency = _parse_price_text(regular.get_text(" ", strip=True))
        if price is not None and currency:
            return price, currency

    for source in (aria, text):
        match = ARIA_PRICE_PATTERN.search(source)
        if match:
            left, amount, right = match.group(1), match.group(2), match.group(3)
            currency = _symbol_to_currency(left or right or "")
            price = _to_decimal(amount, currency=currency)
            if price is not None and currency:
                return price, currency
        price, currency = _parse_price_text(source)
        if price is not None and currency:
            return price, currency
    return None, ""


def _parse_price_text(value: str) -> tuple[Decimal | None, str]:
    text = " ".join(str(value or "").split())
    if not text:
        return None, ""
    # Prefer first currency-marked amount (active price usually listed before struck-through).
    match = re.search(
        r"([€£$¥]|USD|EUR|GBP|JPY)\s*([\d.,\s]+)|([\d.,\s]+)\s*([€£$¥]|USD|EUR|GBP|JPY|円)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, ""
    if match.group(1):
        currency = _symbol_to_currency(match.group(1))
        amount = match.group(2)
    else:
        currency = _symbol_to_currency(match.group(4))
        amount = match.group(3)
    price = _to_decimal(amount, currency=currency)
    return price, currency


def _symbol_to_currency(token: str) -> str:
    raw = str(token or "").strip()
    if raw in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[raw]
    upper = raw.upper()
    if upper in {"USD", "EUR", "GBP", "JPY"}:
        return upper
    return ""


def _to_decimal(amount: str, *, currency: str) -> Decimal | None:
    raw = str(amount or "").strip()
    if not raw:
        return None
    # European thousands/decimal: 1.234,56 vs US 1,234.56 vs JPY 109,100
    cleaned = raw.replace(" ", "").replace("\u00a0", "")
    if currency == "JPY":
        cleaned = cleaned.replace(",", "").replace(".", "")
    elif "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and currency in {"EUR", "GBP"}:
        # Ambiguous single separator: treat as decimal when 2 digits after comma.
        if re.search(r",\d{2}$", cleaned):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _extract_condition(text: str) -> str:
    match = CONDITION_PATTERN.search(text or "")
    if not match:
        return ""
    value = match.group(1)
    mapping = {
        "never worn": "New",
        "pristine": "Excellent",
        "excellent": "Excellent",
        "very good": "Very Good",
        "good": "Good",
        "fair": "Fair",
        "satisfactory": "Good",
        "correct": "Good",
        "used": "Used",
    }
    return mapping.get(value.lower(), value.title())


def _infer_brand(title: str, url: str) -> str:
    haystack = f"{title} {url}".lower()
    for needle, brand in BRAND_MARKERS:
        if needle in haystack:
            return brand
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) >= 2:
        return parts[-2].replace("-", " ").title()
    return ""


def _infer_category(title: str, url: str) -> str:
    path = urlparse(url).path.lower()
    title_l = title.lower()
    if "wallet" in title_l or "purse" in path or "card" in title_l:
        return "Wallet"
    if "backpack" in title_l or "backpack" in path:
        return "Backpack"
    if "tote" in title_l:
        return "Tote Bag"
    if "clutch" in title_l or "pouch" in title_l:
        return "Clutch"
    if "shoulder" in title_l:
        return "Shoulder Bag"
    if "bag" in title_l or "/bags" in path or "handbag" in path:
        return "Bag"
    return "Bag"


def _external_id_from_url(url: str) -> str:
    match = PRODUCT_ID_PATTERN.search(url)
    return match.group(1) if match else url.rstrip("/").split("/")[-1]


def _classify_blocking_page(html: str) -> BlockingReason | None:
    lowered = (html or "").lower()
    has_products = bool(
        re.search(r"catalog__productcard__|productcard__|-\d{5,}\.shtml", lowered)
    )
    if has_products:
        return None
    if any(token in lowered for token in ("captcha", "cf-challenge", "challenge-platform", "hcaptcha")):
        return BlockingReason.CAPTCHA_REQUIRED
    if any(token in lowered for token in ("sign in to continue", "create an account", "login-wall", "auth0")):
        return BlockingReason.POLICY_RESTRICTION
    if any(
        token in lowered
        for token in (
            "consent management",
            "cookie consent",
            "didomi",
            "onetrust",
            "accept all cookies",
            "we use cookies",
        )
    ) and "productcard" not in lowered:
        # Consent-only shell without listings.
        return BlockingReason.POLICY_RESTRICTION
    return None


def _looks_malformed(html: str) -> bool:
    text = (html or "").strip()
    if len(text) < 200:
        return True
    if "<html" not in text.lower() and "vestiaire" not in text.lower():
        return True
    return False
