"""Tests for Chrono24 settings."""

from marketplace.chrono24_settings import Chrono24Settings


def _settings(**overrides) -> Chrono24Settings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="chrono24_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_reserved=False,
        include_negotiable_only=False,
        include_discounted_only=False,
        require_verified_seller=False,
        require_trusted_seller=False,
        include_private_sellers=True,
        include_professional_dealers=True,
    )
    defaults.update(overrides)
    return Chrono24Settings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.include_private_sellers is True
    assert s.include_professional_dealers is True


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(0) == 20


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.CHRONO24_ENABLED", True)
    monkeypatch.setattr("config.settings.CHRONO24_REQUIRE_TRUSTED_SELLER", True)
    s = Chrono24Settings.from_env()
    assert s.enabled is True
    assert s.require_trusted_seller is True
