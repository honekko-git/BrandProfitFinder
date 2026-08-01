"""Tests for comparable diagnostics in browser output."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.connectors.models import MarketListing
from marketplace.importers.manual_importer import ManualImporter
from profit_discovery.discovery_validation.real_profit_verification import build_real_profit_verifications

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def _manual_listing() -> MarketListing:
    return ManualImporter().create_listing(
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        condition="Used",
        price="695",
        currency="USD",
        market_name="Fashionphile",
        url="https://www.fashionphile.com/p/chanel-classic-wallet-black-caviar-manual",
    )


def test_rejection_reasons_and_accepted_count_in_result() -> None:
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    queries = [
        "シャネル キャビアスキン 財布 黒",
        "シャネル クラシック 財布",
        "CHANEL wallet caviar black",
    ]
    results = build_real_profit_verifications(
        brand="Chanel",
        category="Wallet",
        manual_listing=_manual_listing(),
        yahoo_html_by_query={query: yahoo_html for query in queries},
    )
    item = results[0]
    assert item.purchase_subtype == "COMPACT_WALLET"
    assert item.purchase_material == "Caviar"
    assert item.yahoo_live_sample_count >= 3
    assert item.yahoo_rejected_sample_count >= 0
    # Fixture contains many accessory / 1円 / hard-excluded wallet comps.
    # When matching accepts none, median stays 0 (do not invent a price).
    if item.yahoo_accepted_comparables:
        assert item.comparable_median_jpy > 0
    else:
        assert item.yahoo_rejected_sample_count > 0
        assert item.comparable_median_jpy == Decimal("0")
    if item.yahoo_rejected_sample_count:
        assert item.yahoo_rejected_samples


def test_comparable_median_and_warning_fields_present() -> None:
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    results = build_real_profit_verifications(
        brand="Chanel",
        category="Wallet",
        manual_listing=_manual_listing(),
        yahoo_html_by_query={"シャネル クラシック 財布": yahoo_html},
    )
    item = results[0]
    assert item.comparable_median_jpy == item.domestic_median_jpy
    assert item.legacy_median_jpy >= Decimal("0")
    assert item.comparable_data_warning in {"", "COMPARABLE_DATA_SUSPECT"}
