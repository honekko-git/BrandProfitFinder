"""Tests for Vestiaire settings."""

import pytest

from marketplace.vestiaire_settings import VestiaireSettings


def _settings(**overrides) -> VestiaireSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="vestiaire_search_normal.json",
        allow_unknown_currency=False,
        include_inactive=False,
        include_sold=False,
    )
    defaults.update(overrides)
    return VestiaireSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.page_size == 20
    assert s.default_currency == "JPY"


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(1) == 1
    assert _settings().validate_page_size(100) == 50


def test_max_pages_bounds() -> None:
    assert _settings().validate_max_pages(0) == 1
    assert _settings().validate_max_pages(100) == 20


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.VESTIAIRE_ENABLED", True)
    monkeypatch.setattr("config.settings.VESTIAIRE_PAGE_SIZE", 15)
    s = VestiaireSettings.from_env()
    assert s.enabled is True
    assert s.page_size == 15
