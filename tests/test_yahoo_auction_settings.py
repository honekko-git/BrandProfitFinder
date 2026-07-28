"""Unit tests for Yahoo Auction settings."""

import pytest

from marketplace.yahoo_auction_settings import YahooAuctionConfig


def _config(**overrides) -> YahooAuctionConfig:
    defaults = dict(
        enabled=True,
        demo_enabled=False,
        data_source="",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="end_time",
    )
    defaults.update(overrides)
    return YahooAuctionConfig(**defaults)


def test_enabled_flag() -> None:
    assert _config(enabled=True).enabled is True
    assert _config(enabled=False).enabled is False


def test_demo_enabled_flag() -> None:
    assert _config(demo_enabled=True).can_demo is True
    assert _config(enabled=False, demo_enabled=True).can_demo is False


def test_hits_lower_bound() -> None:
    assert _config().validate_hits(1) == 1
    assert _config().validate_hits(0) == 1


def test_hits_upper_bound() -> None:
    assert _config().validate_hits(30) == 30
    assert _config().validate_hits(100) == 30


def test_page_lower_bound() -> None:
    assert _config().validate_page(1) == 1
    assert _config().validate_page(0) == 1


def test_page_upper_bound() -> None:
    assert _config().validate_page(100) == 100
    assert _config().validate_page(200) == 100


def test_timeout_and_retries() -> None:
    config = _config(timeout_seconds=15, max_retries=3)
    assert config.timeout_seconds == 15
    assert config.max_retries == 3


def test_no_live_data_source() -> None:
    config = _config(data_source="")
    assert config.has_live_data_source is False
    assert config.can_execute_live is False


def test_live_data_source_configured() -> None:
    config = _config(data_source="official-feed")
    assert config.has_live_data_source is True
    assert config.can_execute_live is True


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_ENABLED", True)
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_DEMO_ENABLED", True)
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_DATA_SOURCE", "fixture-provider")
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_HITS", 15)
    config = YahooAuctionConfig.from_env()
    assert config.enabled is True
    assert config.demo_enabled is True
    assert config.data_source == "fixture-provider"
    assert config.hits == 15
