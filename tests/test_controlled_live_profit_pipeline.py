"""Pipeline tests for controlled live profit verification."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html
from marketplace.browser_acquisition.matching import build_yahoo_search_terms
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.discovery_validation.controlled_live_verification import (
    build_controlled_live_verifications,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def _yahoo_html_map(html: str, titles: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for title in titles:
        mapping[build_yahoo_search_terms(title=title, brand="Chanel", category="Wallet")] = html
    return mapping


def test_controlled_live_profit_pipeline_matches_profit_calculator() -> None:
    purchase_html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    titles = [listing.title for listing in parse_fashionphile_html(purchase_html)]
    results, blocking = build_controlled_live_verifications(
        brand="Chanel",
        category="Wallet",
        purchase_html=purchase_html,
        yahoo_html_by_query=_yahoo_html_map(yahoo_html, titles),
    )

    assert blocking == ""
    assert results
    item = results[0]
    assert item.yahoo_matched_samples >= 1

    listing = parse_fashionphile_html(purchase_html)[0]
    product = Product(
        name=listing.title,
        brand=listing.brand,
        price=float(listing.price),
        currency=listing.currency,
        store_name="Fashionphile",
        url=listing.url,
        exchange_rate=160.0,
    )
    baseline = ProfitCalculator().calculate(
        product,
        item.median_selling_price_jpy,
        domestic_market="yahoo_auction",
    )
    assert item.estimated_profit == baseline.profit_jpy
    assert item.profit_margin == baseline.profit_margin
    assert item.roi == baseline.roi
    assert item.decision in {"BUY", "HOLD", "PASS"} or item.decision.startswith("PROVISIONAL")
