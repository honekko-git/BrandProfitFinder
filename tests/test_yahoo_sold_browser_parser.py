"""Tests for Yahoo sold browser HTML parsing."""

from __future__ import annotations

from pathlib import Path

from marketplace.browser_acquisition.yahoo_sold_acquirer import (
    YahooSoldAcquirer,
    parse_yahoo_sold_html,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_parse_yahoo_sold_prices() -> None:
    html = (FIXTURES / "yahoo_sold_results.html").read_text(encoding="utf-8")
    samples, strategy = parse_yahoo_sold_html(html)

    assert strategy
    assert len(samples) >= 2
    assert all(sample.sold_price_jpy > 0 for sample in samples)
    assert samples[0].title
    assert "wallet" in samples[0].title.lower() or "CHANEL" in samples[0].title


def test_parse_yahoo_excludes_current_listings() -> None:
    html = (FIXTURES / "yahoo_sold_results.html").read_text(encoding="utf-8")
    samples, _strategy = parse_yahoo_sold_html(html)
    titles = [sample.title for sample in samples]
    assert not any("現在" in title for title in titles)


def test_parse_yahoo_empty_result() -> None:
    html = (FIXTURES / "yahoo_empty.html").read_text(encoding="utf-8")
    samples, _strategy = parse_yahoo_sold_html(html)
    assert samples == []

    result = YahooSoldAcquirer().acquire(search_terms="Chanel wallet", html=html)
    assert result.status.value == "BLOCKED"
    assert result.blocking_reason == "SOLD_PRICE_NOT_AVAILABLE"
