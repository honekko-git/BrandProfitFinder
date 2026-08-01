"""Mercari listing acquisition and parsing."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserFetchResult, BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.matching import is_excluded_title
from marketplace.browser_acquisition.mercari_search_queries import (
    MAX_SEARCH_QUERIES,
    build_mercari_search_queries,
)
from marketplace.browser_acquisition.models import AcquisitionResult, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.rate_limit import RateLimiter

MERCARI_SEARCH_URL = "https://jp.mercari.com/search?keyword={query}&status={status}"
MERCARI_ITEM_URL = "https://jp.mercari.com/item/{item_id}"
DEFAULT_LISTING_LIMIT = 20
DEFAULT_STATUS = "sold_out|trading"
FALLBACK_STATUS = "on_sale"
SOURCE_NAME = "Mercari"

ITEM_ID_PATTERN = re.compile(r"/item/(m[0-9]+)", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"(?:¥|￥|円)\s*([0-9][0-9,]*)|([0-9][0-9,]*)\s*円")

CONDITION_BY_ID = {
    1: "New",
    2: "Like New",
    3: "Very Good",
    4: "Good",
    5: "Fair",
    6: "Poor",
}


def parse_mercari_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = SOURCE_NAME,
    auction_status: str = "sold_out",
) -> list[YahooSoldSample]:
    """Parse Mercari search HTML into domestic comparable samples."""
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    soup = BeautifulSoup(html, "lxml")
    samples: list[YahooSoldSample] = []
    seen: set[str] = set()

    for node in soup.select("mer-item-thumbnail"):
        sample = _sample_from_thumbnail(node, timestamp, source, auction_status=auction_status)
        if sample is None:
            continue
        key = sample.url or f"{sample.title}|{sample.sold_price_jpy}"
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)

    if samples:
        return samples

    for cell in soup.select("[data-testid='item-cell'], li[data-testid='item-cell']"):
        sample = _sample_from_cell(cell, timestamp, source, auction_status=auction_status)
        if sample is None:
            continue
        key = sample.url or f"{sample.title}|{sample.sold_price_jpy}"
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)

    if samples:
        return samples

    for anchor in soup.select("a[href*='/item/']"):
        sample = _sample_from_anchor(anchor, timestamp, source, auction_status=auction_status)
        if sample is None:
            continue
        key = sample.url or f"{sample.title}|{sample.sold_price_jpy}"
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)
    return samples


class MercariAcquirer:
    """Acquire Mercari listings via HTML fixtures or live mercapi search."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = MERCARI_SEARCH_URL,
        listing_limit: int = DEFAULT_LISTING_LIMIT,
        max_search_queries: int = MAX_SEARCH_QUERIES,
        rate_limiter: RateLimiter | None = None,
        prefer_sold: bool = True,
    ) -> None:
        self._browser = browser or BrowserSession()
        self._search_url_template = search_url_template
        self._listing_limit = listing_limit
        self._max_search_queries = max_search_queries
        self._rate_limiter = rate_limiter or RateLimiter(min_interval_seconds=2.0)
        self._prefer_sold = prefer_sold

    def acquire(
        self,
        *,
        search_terms: str,
        html: str | None = None,
        search_url: str | None = None,
        fetch_result: BrowserFetchResult | None = None,
        status: str = DEFAULT_STATUS,
    ) -> AcquisitionResult:
        """Acquire Mercari listings for one search query."""
        query = search_terms.strip()
        url = search_url or self._search_url_template.format(
            query=quote_plus(query),
            status=quote_plus(status),
        )

        if html is not None:
            samples = parse_mercari_html(html)[: self._listing_limit]
            if not samples:
                return AcquisitionResult(
                    status=AcquisitionStatus.BLOCKED,
                    blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                    detail="No Mercari listings found in HTML",
                    search_query=query,
                    source=SOURCE_NAME,
                )
            return AcquisitionResult(
                status=AcquisitionStatus.LIVE,
                samples=tuple(samples),
                search_query=query,
                source=SOURCE_NAME,
            )

        live_samples = self._fetch_live_api(query)
        if live_samples:
            return AcquisitionResult(
                status=AcquisitionStatus.LIVE,
                samples=tuple(live_samples[: self._listing_limit]),
                search_query=query,
                source=SOURCE_NAME,
            )

        fetch = fetch_result or self._browser.fetch_html(url)
        if fetch.blocked_reason:
            reason = BlockingReason(fetch.blocked_reason)
            raise AcquisitionBlockedError(reason, fetch.url)
        samples = parse_mercari_html(fetch.html)[: self._listing_limit]
        if not samples:
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No Mercari listings found",
                search_query=query,
                source=SOURCE_NAME,
            )
        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            samples=tuple(samples),
            search_query=query,
            source=SOURCE_NAME,
        )

    def acquire_multi(
        self,
        *,
        title: str,
        brand: str,
        category: str,
        queries: list[str] | None = None,
        html_by_query: dict[str, str] | None = None,
    ) -> tuple[list[YahooSoldSample], list[str]]:
        """Run up to three Mercari searches and merge samples."""
        search_queries = (queries or build_mercari_search_queries(title=title, brand=brand, category=category))[
            : self._max_search_queries
        ]
        html_map = html_by_query or {}
        if html_map:
            search_queries = [query for query in search_queries if query in html_map] or list(html_map.keys())[
                : self._max_search_queries
            ]

        merged: list[YahooSoldSample] = []
        seen: set[str] = set()
        for query in search_queries:
            html = html_map.get(query)
            try:
                if html is not None:
                    result = self.acquire(search_terms=query, html=html)
                else:
                    self._rate_limiter.wait()
                    result = self.acquire(search_terms=query)
            except AcquisitionBlockedError:
                continue
            except Exception:
                # Playwright/binary/network failures must not discard the query list.
                continue
            for sample in result.samples:
                key = sample.url or f"{sample.title}|{sample.sold_price_jpy}"
                if key in seen:
                    continue
                if is_excluded_title(sample.title):
                    continue
                seen.add(key)
                merged.append(sample)
                if len(merged) >= self._listing_limit:
                    return merged, search_queries
        return merged, search_queries

    def _fetch_live_api(self, query: str) -> list[YahooSoldSample]:
        """Fetch listings through mercapi when available."""
        try:
            from mercapi import Mercapi
            from mercapi.requests.search import SearchRequestData
        except ImportError:
            return []

        def _run() -> list[YahooSoldSample]:
            return asyncio.run(self._search_mercapi(Mercapi(), SearchRequestData, query))

        try:
            asyncio.get_running_loop()
            in_async = True
        except RuntimeError:
            in_async = False

        try:
            if in_async:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    return executor.submit(_run).result()
            return _run()
        except Exception:
            return []

    async def _search_mercapi(self, client, request_data, query: str) -> list[YahooSoldSample]:
        timestamp = datetime.now(tz=UTC).isoformat()
        statuses = []
        if self._prefer_sold:
            statuses.append(request_data.Status.STATUS_SOLD_OUT)
        else:
            statuses.append(request_data.Status.STATUS_ON_SALE)

        samples: list[YahooSoldSample] = []
        seen: set[str] = set()
        for status in statuses:
            results = await client.search(query, status=[status])
            for item in list(results.items)[: self._listing_limit]:
                sample = _sample_from_api_item(item, timestamp)
                if sample is None:
                    continue
                key = sample.url or f"{sample.title}|{sample.sold_price_jpy}"
                if key in seen:
                    continue
                seen.add(key)
                samples.append(sample)
                if len(samples) >= self._listing_limit:
                    return samples
            if samples:
                break
        return samples


def _sample_from_api_item(item, timestamp: str) -> YahooSoldSample | None:
    item_id = str(getattr(item, "id_", "") or "").strip()
    title = str(getattr(item, "name", "") or "").strip()
    price = int(getattr(item, "price", 0) or 0)
    if not title or price <= 0:
        return None
    if is_excluded_title(title):
        return None
    condition_id = int(getattr(item, "item_condition_id", 0) or 0)
    thumbnails = getattr(item, "thumbnails", None) or []
    image_url = str(thumbnails[0]) if thumbnails else ""
    seller_id = str(getattr(item, "seller_id", "") or "")
    status = str(getattr(item, "status", "") or "")
    auction_status = "sold" if "SOLD" in status.upper() else "active"
    if item_id.startswith("m"):
        url = MERCARI_ITEM_URL.format(item_id=item_id)
    elif item_id:
        url = f"https://jp.mercari.com/shops/product/{item_id}"
    else:
        url = ""
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=timestamp,
        source=SOURCE_NAME,
        condition=CONDITION_BY_ID.get(condition_id, ""),
        url=url,
        auction_status=auction_status,
        seller=seller_id,
        image_url=image_url,
    )


def _sample_from_thumbnail(
    node,
    timestamp: str,
    source: str,
    *,
    auction_status: str = "sold_out",
) -> YahooSoldSample | None:
    title = (node.get("item-name") or node.get("aria-label") or "").strip()
    price_raw = node.get("price") or ""
    price = _parse_price(str(price_raw))
    image_url = (node.get("src") or node.get("thumbnail") or "").strip()
    anchor = node.find_parent("a") or node.find("a")
    href = anchor.get("href") if anchor is not None else ""
    url = _absolute_item_url(href)
    if not title:
        title = _title_from_anchor(anchor) if anchor is not None else ""
    if not title or price <= 0:
        return None
    if is_excluded_title(title):
        return None
    parent_text = node.find_parent("li").get_text(" ", strip=True) if node.find_parent("li") else ""
    condition = _detect_condition(parent_text)
    seller = _detect_seller(parent_text)
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=timestamp,
        source=source,
        condition=condition,
        url=url,
        auction_status=auction_status,
        seller=seller,
        image_url=image_url,
    )


def _sample_from_cell(
    cell,
    timestamp: str,
    source: str,
    *,
    auction_status: str = "sold_out",
) -> YahooSoldSample | None:
    thumb = cell.select_one("mer-item-thumbnail")
    if thumb is not None:
        return _sample_from_thumbnail(thumb, timestamp, source, auction_status=auction_status)
    anchor = cell.select_one("a[href*='/item/']")
    if anchor is None:
        return None
    return _sample_from_anchor(
        anchor,
        timestamp,
        source,
        container_text=cell.get_text(" ", strip=True),
        auction_status=auction_status,
    )


def _sample_from_anchor(
    anchor,
    timestamp: str,
    source: str,
    *,
    container_text: str = "",
    auction_status: str = "sold_out",
) -> YahooSoldSample | None:
    href = anchor.get("href") or ""
    url = _absolute_item_url(href)
    if not url:
        return None
    title = _title_from_anchor(anchor)
    text = container_text or anchor.parent.get_text(" ", strip=True) if anchor.parent else anchor.get_text(" ", strip=True)
    price = _parse_price(text)
    if not title or price <= 0:
        return None
    if is_excluded_title(title):
        return None
    image = anchor.select_one("img")
    image_url = (image.get("src") if image is not None else "") or ""
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=timestamp,
        source=source,
        condition=_detect_condition(text),
        url=url,
        auction_status=auction_status,
        seller=_detect_seller(text),
        image_url=image_url,
    )


def _title_from_anchor(anchor) -> str:
    if anchor is None:
        return ""
    title = anchor.get("aria-label") or ""
    if title.strip():
        return title.strip()
    text = anchor.get_text(" ", strip=True)
    if text:
        return text
    img = anchor.select_one("img[alt]")
    if img is not None and img.get("alt"):
        return str(img.get("alt")).strip()
    return ""


def _absolute_item_url(href: str) -> str:
    value = (href or "").strip()
    if not value:
        return ""
    match = ITEM_ID_PATTERN.search(value)
    if match:
        return MERCARI_ITEM_URL.format(item_id=match.group(1))
    if value.startswith("http"):
        return value
    if value.startswith("/"):
        return "https://jp.mercari.com" + value
    return ""


def _parse_price(text: str) -> int:
    raw = (text or "").replace(",", "").strip()
    if raw.isdigit():
        return int(raw)
    match = PRICE_PATTERN.search(text or "")
    if not match:
        return 0
    digits = match.group(1) or match.group(2) or ""
    digits = digits.replace(",", "")
    return int(digits) if digits.isdigit() else 0


def _detect_condition(text: str) -> str:
    lowered = text.lower()
    mapping = (
        ("未使用に近い", "Like New"),
        ("新品", "New"),
        ("未使用", "New"),
        ("目立った傷や汚れなし", "Very Good"),
        ("やや傷や汚れあり", "Good"),
        ("傷や汚れあり", "Fair"),
        ("全体的に状態が悪い", "Poor"),
        ("very good", "Very Good"),
        ("like new", "Like New"),
        ("excellent", "Excellent"),
    )
    for marker, label in mapping:
        if marker.lower() in lowered or marker in text:
            return label
    return ""


def _detect_seller(text: str) -> str:
    match = re.search(r"(?:出品者|seller)[:：\s]*([A-Za-z0-9_\-]+)", text or "", re.IGNORECASE)
    return match.group(1) if match else ""
