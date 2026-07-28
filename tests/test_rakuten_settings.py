"""Unit tests for Rakuten API settings."""

import pytest

from marketplace.rakuten_settings import RakutenConfig


def _config(**overrides) -> RakutenConfig:
    defaults = dict(
        application_id="dummy-app-id",
        access_key="dummy-access-key",
        affiliate_id="",
        base_url="https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
        timeout_seconds=10,
        max_retries=2,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


def test_full_configuration() -> None:
    config = _config(affiliate_id="optional-affiliate")
    assert config.is_configured is True
    assert config.can_execute is True


def test_missing_application_id() -> None:
    config = _config(application_id="")
    assert config.is_configured is False


def test_missing_access_key() -> None:
    config = _config(access_key="")
    assert config.is_configured is False


def test_affiliate_id_optional() -> None:
    config = _config(affiliate_id="")
    assert config.is_configured is True


def test_hits_lower_bound() -> None:
    assert _config().validate_hits(1) == 1
    assert _config().validate_hits(0) == 1


def test_hits_upper_bound() -> None:
    assert _config().validate_hits(30) == 30
    assert _config().validate_hits(100) == 30


def test_page_range() -> None:
    assert _config().validate_page(1) == 1
    assert _config().validate_page(100) == 100
    assert _config().validate_page(0) == 1
    assert _config().validate_page(200) == 100


def test_timeout_and_retries() -> None:
    config = _config(timeout_seconds=15, max_retries=3)
    assert config.timeout_seconds == 15
    assert config.max_retries == 3


def test_bool_enabled_flags() -> None:
    assert _config(enabled=False).can_execute is False
    assert _config(enabled=True, demo_enabled=True).can_demo is True


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.RAKUTEN_APPLICATION_ID", "env-app")
    monkeypatch.setattr("config.settings.RAKUTEN_ACCESS_KEY", "env-key")
    config = RakutenConfig.from_env()
    assert config.application_id == "env-app"
    assert config.access_key == "env-key"
