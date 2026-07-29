"""Tests for brand-category query resolution."""

from __future__ import annotations

from profit_discovery.category_catalog import BrandCategoryResolver, CategoryProfile, CategoryPriority


def test_brand_category_resolver_builds_wallet_query() -> None:
    resolver = BrandCategoryResolver()

    assert resolver.build_query("Chanel", "Wallet") == "Chanel Wallet"


def test_brand_category_resolver_builds_bag_query() -> None:
    resolver = BrandCategoryResolver()

    assert resolver.build_query("Hermes", "Bag") == "Hermes Bag"


def test_brand_category_resolver_generates_brand_category_targets() -> None:
    resolver = BrandCategoryResolver()
    categories = [
        CategoryProfile(name="Wallet", priority=CategoryPriority.HIGH.value),
        CategoryProfile(name="Mini Bag", priority=CategoryPriority.HIGH.value),
    ]

    targets = resolver.resolve(["Chanel", "Gucci"], categories)

    assert len(targets) == 4
    assert targets[0].query == "Chanel Wallet"
    assert targets[1].query == "Chanel Mini Bag"
    assert targets[2].query == "Gucci Wallet"
    assert targets[3].query == "Gucci Mini Bag"


def test_brand_category_resolver_skips_brand_restricted_categories() -> None:
    resolver = BrandCategoryResolver()
    categories = [
        CategoryProfile(
            name="Kelly Bag",
            priority=CategoryPriority.HIGH.value,
            target_brands=("Hermes",),
        ),
    ]

    targets = resolver.resolve(["Chanel", "Hermes"], categories)

    assert len(targets) == 1
    assert targets[0].brand == "Hermes"
    assert targets[0].query == "Hermes Kelly Bag"
