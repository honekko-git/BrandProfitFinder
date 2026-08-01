"""Yahoo Auction sold-price acquisition and parsing."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserFetchResult, BrowserSession
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.matching import is_excluded_title
from marketplace.browser_acquisition.models import AcquisitionResult, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_diagnostics import (
    PARSER_STRATEGY_AUCTION_CONTAINER,
    PARSER_STRATEGY_JSON_LD,
    PARSER_STRATEGY_LEGACY,
    YahooParseDiagnostics,
    build_yahoo_parse_diagnostics,
)
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries

YAHOO_CLOSED_SEARCH_URL = "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={query}"
DEFAULT_SOLD_LIMIT = 20
MAX_SEARCH_QUERIES = 4

CURRENT_LISTING_MARKERS = ("現在", "即決", "残り", "入札中", "開催中")
NOISE_MARKERS = ("広告", "おすすめ", "新品通販", "関連検索", "ページ", "前へ", "次へ")
AUCTION_ID_PATTERN = re.compile(r"/jp/auction/([^/?#]+)", re.IGNORECASE)


def parse_yahoo_sold_html(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = "Yahoo Auction",
) -> tuple[list[YahooSoldSample], str]:
    """Parse Yahoo closed-search HTML and return samples plus parser strategy used."""
    timestamp = retrieved_at or datetime.now(tz=UTC).isoformat()
    strategies = (
        (_parse_auction_containers, PARSER_STRATEGY_AUCTION_CONTAINER),
        (_parse_json_ld_items, PARSER_STRATEGY_JSON_LD),
        (_parse_legacy_nodes, PARSER_STRATEGY_LEGACY),
    )
    for parser, strategy in strategies:
        samples = _dedupe_samples(parser(html, timestamp, source))
        if samples:
            return samples, strategy
    return [], PARSER_STRATEGY_LEGACY


def parse_yahoo_sold_html_with_strategy(
    html: str,
    *,
    retrieved_at: str | None = None,
    source: str = "Yahoo Auction",
) -> tuple[list[YahooSoldSample], str]:
    """Backward-compatible alias returning samples and strategy label."""
    samples, strategy = parse_yahoo_sold_html(html, retrieved_at=retrieved_at, source=source)
    return samples, strategy


class YahooSoldAcquirer:
    """Acquire sold samples from Yahoo Auction closed search."""

    def __init__(
        self,
        *,
        browser: BrowserSession | None = None,
        search_url_template: str = YAHOO_CLOSED_SEARCH_URL,
        sold_limit: int = DEFAULT_SOLD_LIMIT,
        max_search_queries: int = MAX_SEARCH_QUERIES,
    ) -> None:
        self._browser = browser or BrowserSession()
        self._search_url_template = search_url_template
        self._sold_limit = sold_limit
        self._max_search_queries = max_search_queries
        self.last_diagnostics: list[YahooParseDiagnostics] = []

    def acquire(
        self,
        *,
        search_terms: str,
        html: str | None = None,
        search_url: str | None = None,
        fetch_result: BrowserFetchResult | None = None,
    ) -> AcquisitionResult:
        """Acquire sold samples for one search query."""
        query = search_terms.strip()
        url = search_url or self._search_url_template.format(query=quote_plus(query))
        status_code = 0

        if html is None:
            fetch = fetch_result or self._browser.fetch_html(url)
            if fetch.blocked_reason:
                diagnostics = build_yahoo_parse_diagnostics(
                    html=fetch.html,
                    final_url=fetch.url,
                    http_status=fetch.status_code,
                    parser_strategy="blocked",
                    blocking_reason=fetch.blocked_reason,
                    search_query=query,
                )
                self.last_diagnostics.append(diagnostics)
                reason = BlockingReason(fetch.blocked_reason)
                raise AcquisitionBlockedError(reason, fetch.url)
            html = fetch.html
            status_code = fetch.status_code
            url = fetch.url

        samples, strategy = parse_yahoo_sold_html_with_strategy(html)
        diagnostics = build_yahoo_parse_diagnostics(
            html=html,
            final_url=url,
            http_status=status_code or 200,
            parser_strategy=strategy,
            blocking_reason=BlockingReason.SOLD_PRICE_NOT_AVAILABLE.value if not samples else "",
            search_query=query,
        )
        self.last_diagnostics.append(diagnostics)

        if not samples:
            return AcquisitionResult(
                status=AcquisitionStatus.BLOCKED,
                blocking_reason=BlockingReason.SOLD_PRICE_NOT_AVAILABLE.value,
                detail="No sold prices found on Yahoo closed search page",
                search_query=query,
                source="Yahoo Auction",
            )

        return AcquisitionResult(
            status=AcquisitionStatus.LIVE,
            samples=tuple(samples[: self._sold_limit]),
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
    ) -> tuple[list[YahooSoldSample], list[str], list[YahooParseDiagnostics]]:
        """Run up to max_search_queries searches, merge, dedupe, and return live sold samples."""
        self.last_diagnostics = []
        search_queries = (queries or build_yahoo_search_queries(title=title, brand=brand, category=category))[
            : self._max_search_queries
        ]
        html_map = html_by_query or {}
        if html_map:
            search_queries = [query for query in search_queries if query in html_map]
        merged: list[YahooSoldSample] = []
        seen: set[str] = set()

        for query in search_queries:
            html = html_map.get(query)
            if html is not None:
                samples, strategy = parse_yahoo_sold_html_with_strategy(html)
                diagnostics = build_yahoo_parse_diagnostics(
                    html=html,
                    final_url=self._search_url_template.format(query=quote_plus(query)),
                    http_status=200,
                    parser_strategy=strategy,
                    blocking_reason=BlockingReason.SOLD_PRICE_NOT_AVAILABLE.value if not samples else "",
                    search_query=query,
                )
                self.last_diagnostics.append(diagnostics)
            else:
                try:
                    result = self.acquire(search_terms=query)
                except AcquisitionBlockedError:
                    continue
                samples = list(result.samples)
            for sample in samples:
                key = _dedupe_key(sample)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(sample)
                if len(merged) >= self._sold_limit:
                    return merged, search_queries, self.last_diagnostics

        return merged, search_queries, self.last_diagnostics


def _parse_json_ld_items(html: str, retrieved_at: str, source: str) -> list[YahooSoldSample]:
    soup = BeautifulSoup(html, "lxml")
    samples: list[YahooSoldSample] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "ItemList":
            continue
        for element in payload.get("itemListElement", []):
            if not isinstance(element, dict):
                continue
            url = str(element.get("url", "")).strip()
            if not url:
                continue
            anchor = soup.select_one(f"a[href*='{url.rsplit('/', 1)[-1]}']")
            if anchor is None:
                continue
            sample = _sample_from_anchor(anchor, retrieved_at, source)
            if sample is not None:
                samples.append(sample)
    return samples


def _parse_auction_containers(html: str, retrieved_at: str, source: str) -> list[YahooSoldSample]:
    soup = BeautifulSoup(html, "lxml")
    samples: list[YahooSoldSample] = []
    seen_ids: set[str] = set()
    for anchor in soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        href = anchor.get("href", "").strip()
        match = AUCTION_ID_PATTERN.search(href)
        if not match:
            continue
        listing_id = match.group(1)
        if listing_id in seen_ids:
            continue
        sample = _sample_from_anchor(anchor, retrieved_at, source)
        if sample is None:
            continue
        seen_ids.add(listing_id)
        samples.append(sample)
    return samples


def _parse_legacy_nodes(html: str, retrieved_at: str, source: str) -> list[YahooSoldSample]:
    soup = BeautifulSoup(html, "lxml")
    samples: list[YahooSoldSample] = []
    for node in soup.select("li.Product, .Product, .products__item, tr[data-auction-id]"):
        sample = _parse_product_node(node, retrieved_at, source)
        if sample is not None:
            samples.append(sample)
    return samples


def _sample_from_anchor(anchor, retrieved_at: str, source: str) -> YahooSoldSample | None:
    href = anchor.get("href", "").strip()
    if not AUCTION_ID_PATTERN.search(href):
        return None
    container = _find_listing_container(anchor)
    if container is None:
        return None
    text = container.get_text(" ", strip=True)
    if _is_noise_block(text) or _is_current_listing(text):
        return None
    price = _extract_rakusatsu_price(text)
    if price is None:
        return None
    title = _extract_title(anchor, container)
    if not title or title.lower() == "detail" or len(title) < 8:
        return None
    if is_excluded_title(title):
        return None
    sold_at = _extract_sold_date(text)
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        sold_at=sold_at,
        url=href,
        retrieved_at=retrieved_at,
        source=source,
        auction_status="sold",
    )


def _parse_product_node(node, retrieved_at: str, source: str) -> YahooSoldSample | None:
    anchor = node.select_one("a[href*='auctions.yahoo.co.jp/jp/auction/']")
    if anchor is not None:
        return _sample_from_anchor(anchor, retrieved_at, source)
    text = node.get_text(" ", strip=True)
    if _is_noise_block(text) or _is_current_listing(text):
        return None
    price = _extract_rakusatsu_price(text)
    if price is None:
        return None
    title_node = node.select_one("a, h3")
    title = title_node.get_text(" ", strip=True) if title_node else text[:120]
    if is_excluded_title(title):
        return None
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        sold_at=_extract_sold_date(text),
        url=anchor.get("href", "").strip() if anchor is not None else "",
        retrieved_at=retrieved_at,
        source=source,
        auction_status="sold",
    )


def _find_listing_container(anchor):
    for parent in anchor.parents:
        if parent.name in {"li", "article", "section"}:
            text = parent.get_text(" ", strip=True)
            if "落札" in text and len(text) < 700:
                return parent
        classes = " ".join(parent.get("class", []))
        if any(token in classes.lower() for token in ("item", "product", "result", "listing")):
            text = parent.get_text(" ", strip=True)
            if "落札" in text:
                return parent
        text = parent.get_text(" ", strip=True)
        if "落札" in text and len(text) < 500:
            return parent
    return anchor.find_parent("div")


def _extract_title(anchor, container) -> str:
    for selector in (".Product__title", ".Product__name", "h3", "h2"):
        title_node = container.select_one(selector)
        if title_node is not None:
            text = title_node.get_text(" ", strip=True)
            if len(text) >= 8:
                return text
    best = ""
    for node in container.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        text = node.get_text(" ", strip=True)
        if len(text) > len(best):
            best = text
    return best or anchor.get_text(" ", strip=True)


def _is_noise_block(text: str) -> bool:
    return any(marker in text for marker in NOISE_MARKERS)


def _is_current_listing(text: str) -> bool:
    if "落札" in text:
        return False
    return any(marker in text for marker in CURRENT_LISTING_MARKERS)


def _extract_rakusatsu_price(text: str) -> int | None:
    patterns = (
        r"落札\s*([\d,]+)\s*円",
        r"落札価格\s*([\d,]+)\s*円",
        r"落札\s*¥\s*([\d,]+)",
        r"税込\s*([\d,]+)\s*円",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _parse_price_value(match.group(1))
            if value is not None:
                return value
    return None


def _extract_sold_date(text: str) -> str:
    match = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", text)
    return match.group(1) if match else ""


def _parse_price_value(raw: str) -> int | None:
    try:
        value = int(raw.replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _dedupe_key(sample: YahooSoldSample) -> str:
    listing_id = ""
    match = AUCTION_ID_PATTERN.search(sample.url)
    if match:
        listing_id = match.group(1)
    normalized_title = re.sub(r"\s+", " ", sample.title.strip().lower())
    if listing_id:
        return f"id:{listing_id}"
    if sample.url:
        return f"url:{sample.url}"
    return f"title:{normalized_title}:{sample.sold_price_jpy}"


def _dedupe_samples(samples: list[YahooSoldSample]) -> list[YahooSoldSample]:
    deduped: list[YahooSoldSample] = []
    seen: set[str] = set()
    for sample in samples:
        key = _dedupe_key(sample)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sample)
    return deduped
