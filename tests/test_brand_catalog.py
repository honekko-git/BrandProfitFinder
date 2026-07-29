"""Tests for brand catalog models and queries."""

from __future__ import annotations

from profit_discovery.brand_catalog import BrandCatalog, BrandOpportunityProfile, BrandProfile, BrandTier


def test_brand_catalog_default_seed_contains_all_tiers() -> None:
    catalog = BrandCatalog.default()
    all_brands = catalog.get_all_brands()

    assert len(all_brands) == 15
    assert {brand.tier for brand in all_brands} == {BrandTier.S.value, BrandTier.A.value, BrandTier.B.value}


def test_brand_catalog_get_by_tier_returns_expected_brands() -> None:
    catalog = BrandCatalog.default()

    tier_s = catalog.get_by_tier("S")
    tier_a = catalog.get_by_tier("A")
    tier_b = catalog.get_by_tier("B")

    assert [brand.name for brand in tier_s] == [
        "Chanel",
        "Louis Vuitton",
        "Miu Miu",
        "Hermes",
        "Coach",
    ]
    assert [brand.name for brand in tier_a] == [
        "Dior",
        "Celine",
        "Loewe",
        "Bottega Veneta",
        "Prada",
    ]
    assert [brand.name for brand in tier_b] == [
        "Gucci",
        "Fendi",
        "Balenciaga",
        "Saint Laurent",
        "Burberry",
    ]


def test_brand_catalog_get_enabled_brands_filters_disabled_entries() -> None:
    catalog = BrandCatalog()
    catalog.add_opportunity_profile(
        BrandOpportunityProfile(
            name="Disabled Brand",
            profit_score=50.0,
            demand_score=50.0,
            turnover_score=50.0,
            risk_score=50.0,
            capital_level=BrandTier.B.value,
            enabled=False,
        ),
    )

    enabled_names = [brand.name for brand in catalog.get_enabled_brands()]

    assert "Disabled Brand" not in enabled_names
    assert "Chanel" in enabled_names


def test_brand_catalog_add_brand_appends_new_profile() -> None:
    catalog = BrandCatalog()
    catalog.add_brand(
        BrandProfile(
            name="New Brand",
            tier=BrandTier.A.value,
            categories=("bags",),
        ),
    )

    assert any(brand.name == "New Brand" for brand in catalog.get_all_brands())
    assert "New Brand" in catalog.brand_names_for_tier("A")
