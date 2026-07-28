"""Unit tests for Yahoo API settings."""

import logging

import pytest

from marketplace.yahoo_settings import YahooApiSettings, validate_yahoo_base_url


def test_client_id_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "dummy-client-id")
    settings = YahooApiSettings.from_env()
    assert settings.client_id == "dummy-client-id"


def test_client_id_missing(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "")
    settings = YahooApiSettings.from_env()
    assert not settings.is_configured


def test_timeout_default(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_TIMEOUT_SECONDS", 10)
    settings = YahooApiSettings.from_env()
    assert settings.timeout_seconds == 10


def test_timeout_invalid_raises_on_module_load(monkeypatch) -> None:
    with pytest.raises(ValueError):
        int("not-a-number")


def test_results_default(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_RESULTS", 20)
    settings = YahooApiSettings.from_env()
    assert settings.results == 20


def test_results_clamped(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_RESULTS", 100)
    settings = YahooApiSettings.from_env()
    assert settings.results == 100


def test_enabled_true(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", True)
    settings = YahooApiSettings.from_env()
    assert settings.enabled is True
    assert settings.can_execute is False


def test_enabled_false(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", False)
    settings = YahooApiSettings.from_env()
    assert settings.enabled is False


def test_client_id_not_logged(monkeypatch, caplog) -> None:
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "secret-yahoo-client-id")
    settings = YahooApiSettings.from_env()
    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("settings loaded enabled=%s configured=%s", settings.enabled, settings.is_configured)
    assert "secret-yahoo-client-id" not in caplog.text


def test_validate_yahoo_base_url() -> None:
    url = validate_yahoo_base_url("https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch")
    assert url.startswith("https://")


def test_validate_yahoo_base_url_invalid() -> None:
    with pytest.raises(ValueError, match="invalid Yahoo API base URL"):
        validate_yahoo_base_url("not-a-url")
