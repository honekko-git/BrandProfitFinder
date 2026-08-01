"""Yahoo Auction open/active listing acquisition and parsing."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserFetchResult, BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.matching import is_excluded_title
from marketplace.browser_acquisition.models import AcquisitionResult, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_identity_queries, build_yahoo_search_queries

YAHOO_OPEN_SEARCH_URL = "https://auctions.yahoo.co.jp/search/search?p={query}"
DEFAULT_OPEN_LIMIT = 20
MAX_SEARCH_QUERIES = 4
AUCTION_ID_PATTERN = re.compile(r"/jp/auction/([^/?#]+)", re.IGNORECASE)

CURRENT_MARKERS = ("現在", "即決", "残り", "入札", "入札中", "開催中")
NOISE_MARKERS = ("広告", "おすすめ", "新品通販", "関連検索", "ページ", "前へ", "次へ")


def parse_yahoo_open_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = "Yahoo Auction",
) -> list[YahooSoldSample]:
    """Parse Yahoo open-search HTML into auction samples."""
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    soup = BeautifulSoup(html, "lxml")
    samples: list[YahooSoldSample] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        sample = _sample_from_anchor(anchor, timestamp, source)
        if sample is None:
            continue
        key = sample.url or sample.title
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)
    return samples


class YahooOpenAcquirer:
    """Acquire active Yahoo Auction listings from open search pages."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = YAHOO_OPEN_SEARCH_URL,
        open_limit: int = DEFAULT_OPEN_LIMIT,
        max_search_queries: int = MAX_SEARCH_QUERIES,
    ) -> None:
        self._browser = browser or BrowserSession()
        self._search_url_template = search_url_template
        self._open_limit = open_limit
        self._max_search_queries = max_search_queries

    def acquire(
        self,
        *,
        search_terms: str,
        html: str | None = None,
        search_url: str | None = None,
        fetch_result: BrowserFetchResult | None = None,
    ) -> AcquisitionResult:
        """Acquire open auction listings for one search query."""
        query = search_terms.strip()
        url = search_url or self._search_url_template.format(query=quote_plus(query))

        if html is None:
            fetch = fetch_result or self._browser.fetch_html(url)
            if fetch.blocked_reason:
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            html = fetch.html
            url = fetch.url

        samples = parse_yahoo_open_html(html)[: self._open_limit]
        if not samples:
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SELECTOR_NOT_FOUND.value,
                detail="No open Yahoo auction listings found",
                search_query=query,
                source="Yahoo Auction",
            )
        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            samples=tuple(samples),
            search_query=query,
            source="Yahoo Auction",
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
        """Run up to three open searches and merge samples."""
        search_queries = (queries or build_yahoo_search_queries(title=title, brand=brand, category=category))[
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
                result = self.acquire(search_terms=query, html=html)
            except AcquisitionBlockedError:
                continue
            for sample in result.samples:
                key = sample.url or f"{sample.title}:{sample.sold_price_jpy}"
                if key in seen:
                    continue
                seen.add(key)
                merged.append(sample)
                if len(merged) >= self._open_limit:
                    return merged, search_queries
        return merged, search_queries


def _sample_from_anchor(anchor, retrieved_at: str, source: str) -> YahooSoldSample | None:
    href = anchor.get("href", "").strip()
    if not AUCTION_ID_PATTERN.search(href):
        return None
    container = _find_container(anchor)
    if container is None:
        return None
    text = container.get_text(" ", strip=True)
    if any(marker in text for marker in NOISE_MARKERS):
        return None
    # Prefer active listings; still accept blocks that expose current/buyout prices
    current = _extract_current_price(text)
    buyout = _extract_buyout_price(text)
    price = buyout or current
    if price is None:
        return None
    title = _extract_title(anchor, container)
    if not title or len(title) < 8 or is_excluded_title(title):
        return None
    status = "active"
    if "即決" in text and buyout:
        status = "buy_now"
    elif "入札" in text or "現在" in text:
        status = "auction"
    return YahooSoldSample(
        title=title,
        sold_price_jpy=int(price),
        retrieved_at=retrieved_at,
        source=source,
        url=href,
        condition=_extract_condition(text),
        buyout_price_jpy=buyout,
        bid_count=_extract_bid_count(text),
        auction_status=status,
        seller=_extract_seller(text),
        image_url=_extract_image(container),
    )


def _find_container(anchor):
    for parent in anchor.parents:
        if parent.name in {"li", "article", "section"}:
            return parent
        classes = " ".join(parent.get("class", []))
        if any(token in classes.lower() for token in ("item", "product", "result", "listing")):
            return parent
    return anchor.find_parent("div")


def _extract_title(anchor, container) -> str:
    for selector in (".Product__title", ".Product__name", "h3", "h2"):
        node = container.select_one(selector)
        if node is not None:
            text = node.get_text(" ", strip=True)
            if len(text) >= 8:
                return text
    best = ""
    for node in container.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        text = node.get_text(" ", strip=True)
        if len(text) > len(best):
            best = text
    return best or anchor.get_text(" ", strip=True)


def _extract_current_price(text: str) -> int | None:
    patterns = (
        r"現在\s*([\d,]+)\s*円",
        r"現在価格\s*([\d,]+)\s*円",
        r"現在\s*¥\s*([\d,]+)",
        r"価格\s*([\d,]+)\s*円",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _parse_int(match.group(1))
            if value:
                return value
    return None


def _extract_buyout_price(text: str) -> int | None:
    patterns = (
        r"即決\s*([\d,]+)\s*円",
        r"即決価格\s*([\d,]+)\s*円",
        r"Buy\s*It\s*Now\s*([\d,]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _parse_int(match.group(1))
            if value:
                return value
    return None


def _extract_bid_count(text: str) -> int | None:
    match = re.search(r"入札\s*(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_seller(text: str) -> str:
    match = re.search(r"出品者[:：]\s*(\S+)", text)
    return match.group(1) if match else ""


def _extract_condition(text: str) -> str:
    for token in ("未使用", "新品", "美品", "中古", "傷あり"):
        if token in text:
            return token
    return ""


def _extract_image(container) -> str:
    image = container.select_one("img[src]")
    if image is None:
        return ""
    return str(image.get("src") or "").strip()


def _parse_int(raw: str) -> int | None:
    try:
        value = int(raw.replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None
