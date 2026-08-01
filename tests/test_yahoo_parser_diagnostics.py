"""Tests for Yahoo parser diagnostics."""

from __future__ import annotations

from pathlib import Path

from marketplace.browser_acquisition.yahoo_diagnostics import build_yahoo_parse_diagnostics
from marketplace.browser_acquisition.yahoo_sold_acquirer import parse_yahoo_sold_html

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_diagnostics_report_selector_and_price_counts() -> None:
    html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    samples, strategy = parse_yahoo_sold_html(html)
    diagnostics = build_yahoo_parse_diagnostics(
        html=html,
        final_url="https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=test",
        http_status=200,
        parser_strategy=strategy,
        search_query="test",
    )

    assert diagnostics.result_container_count >= 3
    assert diagnostics.price_text_count > 0
    assert diagnostics.parser_strategy == strategy
    assert diagnostics.http_status == 200
    assert len(samples) >= 3


def test_diagnostics_include_blocking_reason_on_empty_parse() -> None:
    html = (FIXTURES / "yahoo_empty.html").read_text(encoding="utf-8")
    samples, strategy = parse_yahoo_sold_html(html)
    diagnostics = build_yahoo_parse_diagnostics(
        html=html,
        final_url="https://example.invalid",
        http_status=200,
        parser_strategy=strategy,
        blocking_reason="SOLD_PRICE_NOT_AVAILABLE",
        search_query="empty",
    )
    assert samples == []
    assert diagnostics.blocking_reason == "SOLD_PRICE_NOT_AVAILABLE"
