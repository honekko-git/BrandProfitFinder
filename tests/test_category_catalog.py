"""Tests for category catalog models and queries."""

from __future__ import annotations

from profit_discovery.category_catalog import CategoryCatalog, CategoryPriority, CategoryProfile


def test_category_catalog_default_seed_contains_all_priorities() -> None:
    catalog = CategoryCatalog.default()
    categories = catalog.get_all_categories()

    assert len(categories) == 10
    assert {category.priority for category in categories} == {
        CategoryPriority.HIGH.value,
        CategoryPriority.MEDIUM.value,
        CategoryPriority.LOW.value,
    }


def test_category_catalog_get_high_priority_categories() -> None:
    catalog = CategoryCatalog.default()

    high_priority = catalog.get_high_priority_categories()

    assert [category.name for category in high_priority] == [
        "Wallet",
        "Mini Bag",
        "Shoulder Bag",
        "Classic Bag",
        "Vintage Bag",
    ]


def test_category_catalog_get_by_priority_returns_medium_categories() -> None:
    catalog = CategoryCatalog.default()

    medium_priority = catalog.get_by_priority("MEDIUM")

    assert [category.name for category in medium_priority] == [
        "Watch",
        "Jewelry",
        "Shoes",
        "Accessories",
    ]


def test_category_catalog_get_for_brand_respects_target_brands() -> None:
    catalog = CategoryCatalog()
    catalog.add_category(
        CategoryProfile(
            name="Kelly Bag",
            priority=CategoryPriority.HIGH.value,
            target_brands=("Hermes",),
        ),
    )

    hermes_categories = catalog.get_for_brand("Hermes")
    chanel_categories = catalog.get_for_brand("Chanel")

    assert any(category.name == "Kelly Bag" for category in hermes_categories)
    assert all(category.name != "Kelly Bag" for category in chanel_categories)


def test_category_catalog_add_category_appends_profile() -> None:
    catalog = CategoryCatalog()
    catalog.add_category(
        CategoryProfile(
            name="Belt",
            priority=CategoryPriority.LOW.value,
        ),
    )

    assert any(category.name == "Belt" for category in catalog.get_all_categories())
