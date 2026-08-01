"""Diagnostics for Yahoo sold HTML parsing."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

PARSER_STRATEGY_JSON_LD = "json_ld"
PARSER_STRATEGY_AUCTION_CONTAINER = "auction_container"
PARSER_STRATEGY_LEGACY = "legacy"


@dataclass(frozen=True, slots=True)
class YahooParseDiagnostics:
    """Parser diagnostics for one Yahoo fetch attempt."""

    final_url: str
    http_status: int
    page_title: str
    result_container_count: int
    price_text_count: int
    parser_strategy: str
    blocking_reason: str = ""
    search_query: str = ""

    def to_display(self) -> dict[str, str | int]:
        return {
            "final_url": self.final_url,
            "http_status": self.http_status,
            "page_title": self.page_title,
            "result_container_count": self.result_container_count,
            "price_text_count": self.price_text_count,
            "parser_strategy": self.parser_strategy,
            "blocking_reason": self.blocking_reason,
            "search_query": self.search_query,
        }


def build_yahoo_parse_diagnostics(
    *,
    html: str,
    final_url: str,
    http_status: int,
    parser_strategy: str,
    blocking_reason: str = "",
    search_query: str = "",
) -> YahooParseDiagnostics:
    """Build diagnostics from one fetched Yahoo HTML page."""
    soup = BeautifulSoup(html, "lxml")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    containers = _count_result_containers(soup)
    price_text_count = html.count("落札") + html.count("円")
    return YahooParseDiagnostics(
        final_url=final_url,
        http_status=http_status,
        page_title=page_title,
        result_container_count=containers,
        price_text_count=price_text_count,
        parser_strategy=parser_strategy,
        blocking_reason=blocking_reason,
        search_query=search_query,
    )


def _count_result_containers(soup: BeautifulSoup) -> int:
    auction_links = soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']")
    ids: set[str] = set()
    for anchor in auction_links:
        href = anchor.get("href", "")
        match = href.rstrip("/").split("/")[-1]
        if match:
            ids.add(match)
    return len(ids)
