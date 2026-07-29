"""Resolve demand lookup queries from discovery candidates."""

from __future__ import annotations

import re

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_intelligence.demand.models import DemandQuery

NOISE_WORDS: frozenset[str] = frozenset(
    {
        "black",
        "white",
        "red",
        "leather",
        "canvas",
        "used",
        "new",
        "excellent",
        "monogram",
    }
)

PRODUCT_TYPES: tuple[str, ...] = (
    "Shoulder Bag",
    "Classic Bag",
    "Vintage Bag",
    "Mini Bag",
    "Wallet",
    "Watch",
    "Jewelry",
    "Shoes",
    "Accessories",
    "Clothing",
    "Bag",
)

CATEGORY_TO_PRODUCT_TYPE: dict[str, str] = {
    "wallets": "Wallet",
    "wallet": "Wallet",
    "bags": "Bag",
    "bag": "Bag",
    "watches": "Watch",
    "watch": "Watch",
    "jewelry": "Jewelry",
    "shoes": "Shoes",
    "accessories": "Accessories",
    "clothing": "Clothing",
}


class DemandQueryResolver:
    """Build normalized demand queries from discovery candidate products."""

    def resolve(self, candidate: DiscoveryCandidateResult) -> DemandQuery:
        """Resolve one demand query from a discovery candidate."""
        product = candidate.supplier_product
        brand = _normalize_brand(product.brand)
        product_type = _detect_product_type(product.title, product.category)
        normalized_query = f"{brand} {product_type}".strip() if product_type else brand
        return DemandQuery(
            brand=brand,
            product_type=product_type,
            normalized_query=normalized_query,
        )


def _normalize_brand(raw_brand: str) -> str:
    brand = raw_brand.strip()
    if not brand:
        return ""
    if brand.upper() == brand and len(brand) > 1:
        return brand.title()
    return brand


def _detect_product_type(title: str, category: str) -> str:
    cleaned_title = _strip_noise_words(title)
    lowered_title = cleaned_title.lower()
    for product_type in PRODUCT_TYPES:
        if product_type.lower() in lowered_title:
            return product_type

    category_key = category.strip().lower()
    if category_key in CATEGORY_TO_PRODUCT_TYPE:
        return CATEGORY_TO_PRODUCT_TYPE[category_key]

    return ""


def _strip_noise_words(title: str) -> str:
    tokens = re.split(r"[\s/,-]+", title.strip())
    filtered = [token for token in tokens if token and token.lower() not in NOISE_WORDS]
    return " ".join(filtered)
