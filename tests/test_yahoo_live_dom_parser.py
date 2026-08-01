"""Tests for Yahoo live DOM parser using real-page minimal fixture."""

from __future__ import annotations

from pathlib import Path

from marketplace.browser_acquisition.yahoo_diagnostics import (
    PARSER_STRATEGY_AUCTION_CONTAINER,
    PARSER_STRATEGY_JSON_LD,
)
from marketplace.browser_acquisition.yahoo_sold_acquirer import parse_yahoo_sold_html

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_parse_yahoo_live_dom_minimal_fixture() -> None:
    html = (FIXTURES / "yahoo_live_dom_minimal.html").read_text(encoding="utf-8")
    samples, strategy = parse_yahoo_sold_html(html)

    assert strategy == PARSER_STRATEGY_AUCTION_CONTAINER
    assert len(samples) >= 3
    assert all(sample.sold_price_jpy > 0 for sample in samples)
    assert all(sample.title for sample in samples)
    assert all("auctions.yahoo.co.jp" in sample.url for sample in samples if sample.url)


def test_parse_yahoo_live_full_page_fixture() -> None:
    html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    samples, strategy = parse_yahoo_sold_html(html)

    assert strategy in {PARSER_STRATEGY_AUCTION_CONTAINER, PARSER_STRATEGY_JSON_LD}
    assert len(samples) >= 10
    assert not any("現在" in sample.title for sample in samples)


def test_parse_yahoo_live_excludes_current_only_listings() -> None:
    html = (FIXTURES / "yahoo_sold_results.html").read_text(encoding="utf-8")
    samples, _strategy = parse_yahoo_sold_html(html)
    assert all("現在" not in sample.title for sample in samples)
