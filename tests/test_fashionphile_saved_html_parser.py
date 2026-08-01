"""Tests for Fashionphile saved HTML parser."""

from __future__ import annotations

from pathlib import Path

from marketplace.acquisition_workspace.saved_html_parser import FashionphileSavedHtmlParser, parse_saved_html

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_product_card_title_price_condition_url() -> None:
    html = FIXTURES.joinpath("fashionphile_search_results.html").read_text(encoding="utf-8")
    parser = FashionphileSavedHtmlParser()
    parsed = parser.parse(html)
    assert len(parsed) >= 2
    first = parsed[0]
    assert "Chanel Classic Wallet" in first.title
    assert first.purchase_price == 695
    assert first.condition == "Very Good"
    assert "fashionphile.com" in first.purchase_url


def test_json_ld_fallback_for_fashionphile() -> None:
    html = FIXTURES.joinpath("fashionphile_json_ld.html").read_text(encoding="utf-8")
    parsed = FashionphileSavedHtmlParser().parse(html)
    assert len(parsed) == 1
    assert parsed[0].source_name == "Fashionphile"
    assert parsed[0].brand == "Chanel"


def test_captcha_page_rejected() -> None:
    html = "<html><body>Please verify you are human captcha</body></html>"
    parsed, strategy, diagnostics = parse_saved_html(html, filename="blocked.html")
    assert parsed == []
    assert strategy == "blocked"
    assert "CAPTCHA" in diagnostics["blocked_reason"]


def test_no_browser_bypass_only_saved_html() -> None:
    """Parser only processes provided HTML strings; no network calls."""
    html = FIXTURES.joinpath("fashionphile_search_results.html").read_text(encoding="utf-8")
    parsed, strategy, _ = parse_saved_html(html, filename="saved.html")
    assert strategy == "fashionphile_saved_html"
    assert all(item.parser_strategy for item in parsed)
