"""Tests for used luxury mode configuration."""

from __future__ import annotations

from profit_discovery.config.used_luxury import UsedLuxuryModeConfig


def test_used_luxury_mode_config_defaults() -> None:
    config = UsedLuxuryModeConfig.default()

    assert config.enabled is True
    assert config.markets == ("yahoo_auction", "mercari")
    assert config.categories == ("wallet", "bag", "watch", "jewelry")


def test_used_luxury_mode_brand_filtering() -> None:
    config = UsedLuxuryModeConfig.default()

    assert config.brand_names_for_tier("S") == [
        "Chanel",
        "Louis Vuitton",
        "Hermes",
        "Miu Miu",
    ]
    assert config.brand_names_for_tier("A") == [
        "Dior",
        "Celine",
        "Prada",
        "Loewe",
    ]
    assert config.brand_names_for_tier("B") == [
        "Coach",
        "Bottega Veneta",
        "Fendi",
    ]
    filtered = config.filter_brands(["Chanel", "Gucci", "Prada"])
    assert filtered == ["Chanel", "Prada"]


def test_used_luxury_mode_category_filtering() -> None:
    config = UsedLuxuryModeConfig.default()

    high = config.get_categories_by_priority("HIGH")
    medium = config.get_categories_by_priority("MEDIUM")
    low = config.get_categories_by_priority("LOW")

    assert high == ("Wallet", "Classic Bag", "Shoulder Bag", "Mini Bag")
    assert medium == ("Watch", "Jewelry")
    assert low == ("Shoes", "Accessories")
    assert "Clothing" not in high + medium + low

    profiles = config.get_category_profiles_for_priority("HIGH")
    assert [profile.name for profile in profiles] == list(high)


def test_used_luxury_mode_excludes_new_product_markets() -> None:
    config = UsedLuxuryModeConfig.default()

    assert config.is_excluded_market("amazon") is True
    assert config.is_excluded_market("rakuten") is True
    assert config.is_excluded_market("yahoo_shopping") is True
    assert config.is_excluded_market("yahoo_auction") is False
    assert config.is_excluded_market("mercari") is False
