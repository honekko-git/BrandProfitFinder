"""Pipeline tests for manual Fashionphile import with Yahoo live sold data."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.connectors.models import MarketListing
from marketplace.importers.manual_importer import ManualImporter
from profit_discovery.discovery_validation.real_profit_models import DataStatus
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


def test_manual_import_yahoo_live_pipeline_mixed_truth() -> None:
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

    assert results
    item = results[0]
    assert item.actual_purchase_source == DataStatus.IMPORT.value
    assert item.actual_domestic_source == DataStatus.LIVE.value
    assert item.data_status == DataStatus.MIXED.value
    assert item.verification_complete is False
    assert item.yahoo_live_sample_count >= 3
    assert item.domestic_median_jpy > 0
    assert item.estimated_profit is not None
    assert item.decision in {"BUY", "HOLD", "PASS"} or item.decision.startswith("PROVISIONAL")
