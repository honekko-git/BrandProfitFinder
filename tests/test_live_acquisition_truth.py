"""Truth tests for controlled live acquisition."""

from __future__ import annotations

from pathlib import Path

from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html
from marketplace.browser_acquisition.matching import build_yahoo_search_terms
from profit_discovery.discovery_validation.controlled_live_verification import (
    build_controlled_live_verifications,
)
from profit_discovery.discovery_validation.real_profit_models import DataStatus

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def _yahoo_html_map(html: str, titles: list[str]) -> dict[str, str]:
    return {
        build_yahoo_search_terms(title=title, brand="Chanel", category="Wallet"): html
        for title in titles
    }


def test_both_sources_successful_mark_live() -> None:
    purchase_html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    titles = [listing.title for listing in parse_fashionphile_html(purchase_html)]
    results, blocking = build_controlled_live_verifications(
        purchase_html=purchase_html,
        yahoo_html_by_query=_yahoo_html_map(yahoo_html, titles),
    )
    assert blocking == ""
    assert results
    assert results[0].data_status in {DataStatus.LIVE.value, DataStatus.MIXED.value}


def test_one_source_failed_is_not_full_live() -> None:
    purchase_html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    yahoo_html = (FIXTURES / "yahoo_empty.html").read_text(encoding="utf-8")
    titles = [listing.title for listing in parse_fashionphile_html(purchase_html)]
    results, blocking = build_controlled_live_verifications(
        purchase_html=purchase_html,
        yahoo_html_by_query=_yahoo_html_map(yahoo_html, titles),
    )
    assert results
    assert results[0].data_status != DataStatus.LIVE.value
    assert results[0].verification_complete is False


def test_no_silent_fixture_fallback_in_controlled_live() -> None:
    purchase_html = (FIXTURES / "fashionphile_empty.html").read_text(encoding="utf-8")
    results, blocking = build_controlled_live_verifications(purchase_html=purchase_html)
    assert results == []
    assert blocking == "SELECTOR_NOT_FOUND"


def test_verification_complete_requires_live_and_samples() -> None:
    purchase_html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    titles = [listing.title for listing in parse_fashionphile_html(purchase_html)]
    results, _blocking = build_controlled_live_verifications(
        purchase_html=purchase_html,
        yahoo_html_by_query=_yahoo_html_map(yahoo_html, titles),
    )
    assert results
    if results[0].yahoo_matched_samples < 3:
        assert results[0].verification_complete is False
