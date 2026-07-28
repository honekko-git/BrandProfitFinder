"""Tests for Grailed settings."""

from marketplace.grailed_settings import GrailedSettings


def _settings(**overrides) -> GrailedSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="grailed_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_reserved=False,
        include_offer_enabled_only=False,
        include_discounted_only=False,
        require_verified_seller=False,
    )
    defaults.update(overrides)
    return GrailedSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.default_currency == "JPY"
    assert s.require_verified_seller is False


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(100) == 50
    assert _settings().validate_page_size(0) == 20


def test_max_pages_bounds() -> None:
    assert _settings().validate_max_pages(0) == 1


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.GRAILED_ENABLED", True)
    monkeypatch.setattr("config.settings.GRAILED_INCLUDE_OFFER_ENABLED_ONLY", True)
    monkeypatch.setattr("config.settings.GRAILED_REQUIRE_VERIFIED_SELLER", True)
    s = GrailedSettings.from_env()
    assert s.enabled is True
    assert s.include_offer_enabled_only is True
    assert s.require_verified_seller is True
