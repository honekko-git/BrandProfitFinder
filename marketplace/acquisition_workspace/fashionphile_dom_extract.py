"""Fashionphile search-results DOM extraction (mirrors chrome extension selectors)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

CARD_SELECTORS = (
    "div.fp-algolia-product-card",
    "div.card-wrapper.product-card-wrapper",
    "li.ais-Hits-item div.card",
    "article.product-card",
)

PRODUCT_PATH = re.compile(r"/products/[^/?#]+", re.IGNORECASE)
TRACKING_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "_pos",
    "_sid",
    "_ss",
    "variant",
}
ALLOWED_HOSTS = {"fashionphile.com", "www.fashionphile.com"}


@dataclass(frozen=True, slots=True)
class ExtractedFashionphileProduct:
    title: str
    brand: str
    current_price: Decimal
    currency: str
    formatted_price: str
    url: str
    image_url: str = ""
    original_price: Decimal | None = None
    condition: str = ""
    product_id: str = ""
    availability: str = "available"


@dataclass(frozen=True, slots=True)
class FashionphileDomExtractResult:
    ok: bool
    code: str
    products: tuple[ExtractedFashionphileProduct, ...]
    rejected_count: int = 0
    rejection_reasons: dict[str, int] | None = None
    visible_card_count: int = 0


def is_fashionphile_hostname(hostname: str) -> bool:
    host = (hostname or "").lower().removeprefix("www.")
    return host == "fashionphile.com"


def is_fashionphile_product_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not is_fashionphile_hostname(parsed.hostname or ""):
        return False
    return bool(PRODUCT_PATH.search(parsed.path or ""))


def canonicalize_product_url(url: str, *, base: str = "https://www.fashionphile.com") -> str:
    parsed = urlparse(url if "://" in url else f"{base.rstrip('/')}/{url.lstrip('/')}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS and not is_fashionphile_hostname(host):
        raise ValueError("invalid host")
    match = PRODUCT_PATH.search(parsed.path or "")
    if not match:
        raise ValueError("not product")
    path = match.group(0).rstrip("/")
    return urlunparse(("https", "www.fashionphile.com", path, "", "", ""))


def parse_price_text(text: str) -> tuple[Decimal, str, str] | None:
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    if not raw:
        return None
    if re.search(r"/\s*mo|per\s*month|月々|installment", raw, re.IGNORECASE):
        return None
    currency = ""
    if "$" in raw or re.search(r"USD", raw, re.IGNORECASE):
        currency = "USD"
    elif "€" in raw or re.search(r"EUR", raw, re.IGNORECASE):
        currency = "EUR"
    elif "£" in raw or re.search(r"GBP", raw, re.IGNORECASE):
        currency = "GBP"
    elif "¥" in raw or re.search(r"JPY|円", raw, re.IGNORECASE):
        currency = "JPY"
    numeric = re.sub(r"[^0-9.,]", "", raw)
    if not numeric:
        return None
    if "," in numeric and "." in numeric:
        normalized = numeric.replace(",", "")
    elif "," in numeric and "." not in numeric:
        normalized = numeric.replace(",", ".") if re.search(r",\d{2}$", numeric) else numeric.replace(",", "")
    else:
        normalized = numeric
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return amount, currency, raw


def detect_fashionphile_page(*, page_url: str, html: str) -> FashionphileDomExtractResult:
    host = urlparse(page_url).hostname or ""
    if not is_fashionphile_hostname(host):
        return FashionphileDomExtractResult(ok=False, code="NOT_FASHIONPHILE", products=())
    soup = BeautifulSoup(html or "", "lxml")
    cards = _query_cards(soup)
    lowered = (html or "").lower()
    body_text = soup.get_text(" ", strip=True).lower()
    challenge_only = (
        not cards
        and (
            "verify you are human" in lowered
            or "are you a robot" in lowered
            or "h-captcha" in lowered
            or "g-recaptcha-response" in lowered
            or "captcha challenge" in lowered
            or "access denied" in body_text
        )
    )
    if challenge_only:
        return FashionphileDomExtractResult(ok=False, code="CAPTCHA_ONLY", products=())
    path = urlparse(page_url).path or ""
    has_search = "/search" in path.lower() or "q=" in (urlparse(page_url).query or "")
    if not cards:
        if not has_search and "/collections/" not in path.lower() and "/shop" not in path.lower():
            return FashionphileDomExtractResult(ok=False, code="NOT_SEARCH_RESULTS", products=())
        return FashionphileDomExtractResult(ok=False, code="NO_PRODUCTS", products=())
    return FashionphileDomExtractResult(
        ok=True,
        code="OK",
        products=(),
        visible_card_count=len(cards),
    )


def extract_fashionphile_search_dom(*, page_url: str, html: str) -> FashionphileDomExtractResult:
    detection = detect_fashionphile_page(page_url=page_url, html=html)
    if not detection.ok:
        return detection
    soup = BeautifulSoup(html or "", "lxml")
    cards = _query_cards(soup)
    products: list[ExtractedFashionphileProduct] = []
    reasons: dict[str, int] = {}
    seen: set[str] = set()
    for card in cards:
        item, reason = _extract_one(card)
        if item is None:
            reasons[reason or "unknown"] = reasons.get(reason or "unknown", 0) + 1
            continue
        key = item.url
        if key in seen:
            reasons["duplicate"] = reasons.get("duplicate", 0) + 1
            continue
        seen.add(key)
        products.append(item)
    if not products:
        return FashionphileDomExtractResult(
            ok=False,
            code="EXTRACT_FAILED",
            products=(),
            rejected_count=sum(reasons.values()),
            rejection_reasons=reasons,
            visible_card_count=len(cards),
        )
    return FashionphileDomExtractResult(
        ok=True,
        code="OK",
        products=tuple(products),
        rejected_count=sum(reasons.values()),
        rejection_reasons=reasons,
        visible_card_count=len(cards),
    )


def _query_cards(soup: BeautifulSoup) -> list:
    for selector in CARD_SELECTORS:
        nodes = soup.select(selector)
        if nodes:
            # Prefer algolia cards when present.
            if selector.startswith("div.fp-algolia"):
                return list(nodes)
            return list(nodes)
    return []


def _extract_one(card) -> tuple[ExtractedFashionphileProduct | None, str]:
    text = card.get_text(" ", strip=True).lower()
    if re.search(r"\bsold out\b|\bunavailable\b|\bno longer available\b", text):
        return None, "sold_or_unavailable"
    link = (
        card.select_one("a.fp-card__link[href*='/products/']")
        or card.select_one("a.full-unstyled-link[href*='/products/']")
        or card.select_one("a[href*='/products/']")
    )
    if link is None:
        return None, "missing_url"
    href = (link.get("href") or "").strip()
    try:
        url = canonicalize_product_url(href)
    except ValueError:
        return None, "invalid_url"
    if not is_fashionphile_product_url(url):
        return None, "invalid_url"

    name_node = (
        card.select_one(".fp-card__link__product-name")
        or card.select_one(".product-title")
        or card.select_one("h3, h2")
    )
    vendor_node = card.select_one(".fp-card__vendor, .vendor, .card__vendor")
    title = name_node.get_text(" ", strip=True) if name_node else ""
    brand = vendor_node.get_text(" ", strip=True) if vendor_node else ""
    if brand and title and not title.lower().startswith(brand.lower()):
        title = f"{brand} {title}".strip()
    if not title:
        return None, "missing_title"

    sale_node = (
        card.select_one(".price-item--sale")
        or card.select_one("[data-testid='product-price']")
        or card.select_one(".product-price")
        or card.select_one(".price")
    )
    price_text = sale_node.get_text(" ", strip=True) if sale_node else ""
    compare_nodes = card.select(".price-item--regular, s.price-item, .price__compare, del")
    if not price_text:
        price_root = card.select_one(".price, .fp-price-items")
        price_text = price_root.get_text(" ", strip=True) if price_root else ""
        for node in compare_nodes:
            price_text = price_text.replace(node.get_text(" ", strip=True), " ")
    parsed = parse_price_text(price_text)
    if parsed is None:
        return None, "missing_or_invalid_price"
    amount, currency, formatted = parsed
    if not currency:
        return None, "ambiguous_currency"

    original: Decimal | None = None
    for node in compare_nodes:
        cmp = parse_price_text(node.get_text(" ", strip=True))
        if cmp and cmp[0] > amount:
            original = cmp[0]

    condition_node = card.select_one(".fp-condition, .condition, [data-condition]")
    condition = ""
    if condition_node is not None:
        condition = re.sub(r"Cond(ition)?:\s*", "", condition_node.get_text(" ", strip=True), flags=re.I).strip()

    image_node = card.select_one("img.ais-hit--picture, img.fp-injected-primary-image, img")
    image_url = (image_node.get("src") or "") if image_node else ""
    product_id = (
        card.get("data-product-id")
        or card.get("data-variant-id")
        or card.get("data-handle")
        or ""
    )
    return (
        ExtractedFashionphileProduct(
            title=title,
            brand=brand,
            current_price=amount,
            currency=currency,
            formatted_price=formatted,
            url=url,
            image_url=image_url,
            original_price=original,
            condition=condition,
            product_id=str(product_id or ""),
        ),
        "",
    )
