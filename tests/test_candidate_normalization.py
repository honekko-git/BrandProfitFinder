"""Tests for candidate normalization."""

from __future__ import annotations

from decimal import Decimal

from marketplace.acquisition_workspace.normalization import (
    build_detection_fields,
    normalize_brand,
    normalize_category,
    normalize_currency,
    normalize_price,
    normalize_title,
    normalize_url,
)


def test_brand_alias_japanese_and_english() -> None:
    assert normalize_brand("CHANEL") == "Chanel"
    assert normalize_brand("シャネル") == "Chanel"
    assert normalize_brand("chanel") == "Chanel"


def test_category_normalization() -> None:
    assert normalize_category("wallet") == "Wallet"
    assert normalize_category("財布") == "Wallet"
    assert normalize_category("Bag") == "Bag"
    assert normalize_category("bag") == "Bag"
    assert normalize_category("Handbag") == "Bag"
    assert normalize_category("Tote Bag") == "Bag"
    assert normalize_category("Shoulder Bag") == "Bag"
    assert normalize_category("Crossbody Bag") == "Bag"
    assert normalize_category("Flap Bag") == "Bag"
    assert normalize_category("Top Handle Bag") == "Bag"
    assert normalize_category("Boston Bag") == "Bag"
    assert normalize_category("handbag", title="Louis Vuitton Speedy handbag") == "Bag"


def test_non_bag_categories_not_normalized_to_bag() -> None:
    assert normalize_category("Jewelry") == "Jewelry"
    assert normalize_category("Bag", title="Cartier Love Hoop Earrings") == "Jewelry"
    assert normalize_category("Bag", title="Gucci Horsebit Accent Fur Mules") == "Shoes"
    assert normalize_category("Bag", title="Gucci 2019 Wool Sweater") == "Clothing"
    assert normalize_category("Watch") == "Watch"


def test_clothing_category_field_yields_to_title_bag() -> None:
    assert normalize_category("Clothing", title="Gucci Dionysus Bag GG Coated Canvas Small") == "Bag"
    assert normalize_category("Clothing", title="Gucci 2019 Wool Sweater") == "Clothing"


def test_title_cleanup() -> None:
    title = "  CHANEL  Classic   Wallet!!!  "
    normalized = normalize_title(title)
    assert "chanel" in normalized
    assert "classic" in normalized
    assert "!!!" not in normalized


def test_currency_normalization() -> None:
    assert normalize_currency("usd") == "USD"
    assert normalize_currency(" JPY ") == "JPY"


def test_price_normalization() -> None:
    assert normalize_price("$695.00") == Decimal("695.00")
    assert normalize_price("1,200") == Decimal("1200")


def test_url_tracking_removal() -> None:
    url = "https://WWW.Fashionphile.com/p/item/?utm_source=email&gclid=abc#section"
    normalized = normalize_url(url)
    assert "utm_source" not in normalized
    assert "gclid" not in normalized
    assert "#section" not in normalized
    assert normalized.startswith("https://www.fashionphile.com/")


def test_detection_fields_for_wallet() -> None:
    fields = build_detection_fields(
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        condition="Excellent",
    )
    assert fields["brand"] == "Chanel"
    assert fields["category"] == "Wallet"
    assert fields["detected_subtype"] != "UNKNOWN"
