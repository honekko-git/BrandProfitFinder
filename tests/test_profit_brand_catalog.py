"""Tests for profit-demand brand catalog ranking."""

from __future__ import annotations

from profit_discovery.brand_catalog import BrandCatalog, BrandOpportunityProfile


def test_brand_catalog_get_by_opportunity_score_orders_descending() -> None:
    catalog = BrandCatalog.default()

    ranked = catalog.get_by_opportunity_score()

    assert ranked[0].name == "Chanel"
    scores = [profile.calculate_opportunity_score() for profile in ranked]
    assert scores == sorted(scores, reverse=True)


def test_brand_catalog_get_high_demand_brands_returns_threshold_matches() -> None:
    catalog = BrandCatalog.default()

    high_demand = catalog.get_high_demand_brands()

    assert all(profile.demand_score >= 80.0 for profile in high_demand)
    assert any(profile.name == "Chanel" for profile in high_demand)
    assert all(profile.name != "Burberry" for profile in high_demand)


def test_brand_catalog_get_enabled_opportunity_profiles_excludes_disabled() -> None:
    catalog = BrandCatalog()
    catalog.add_opportunity_profile(
        BrandOpportunityProfile(
            name="Disabled Demand Brand",
            profit_score=95.0,
            demand_score=95.0,
            turnover_score=95.0,
            risk_score=10.0,
            capital_level="HIGH",
            enabled=False,
        ),
    )

    enabled = catalog.get_enabled_opportunity_profiles()

    assert all(profile.enabled for profile in enabled)
    assert all(profile.name != "Disabled Demand Brand" for profile in enabled)
