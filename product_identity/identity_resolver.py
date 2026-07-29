"""Resolve product identity keys from discovery candidates."""

from __future__ import annotations

import re

from product_identity.models import ProductIdentity
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult

IDENTITY_NOISE_WORDS: frozenset[str] = frozenset(
    {
        # color
        "black",
        "white",
        "red",
        "blue",
        "green",
        "pink",
        "beige",
        "brown",
        "grey",
        "gray",
        "gold",
        "silver",
        "navy",
        "cream",
        # condition
        "used",
        "new",
        "excellent",
        "good",
        "very",
        "fair",
        "pristine",
        "like",
        # material
        "leather",
        "canvas",
        "caviar",
        "monogram",
        "suede",
        "patent",
        "lamb",
        "calf",
        # seller
        "fashionphile",
        "seller",
        # size
        "sm",
        "md",
        "lg",
        "xl",
        "xs",
        "small",
        "medium",
        "large",
        "mini",
        "mm",
        "pm",
        "gm",
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


class ProductIdentityResolver:
    """Build stable product identity keys from discovery candidates."""

    def resolve(self, candidate: DiscoveryCandidateResult) -> ProductIdentity:
        """Resolve one product identity from a discovery candidate."""
        product = candidate.supplier_product
        brand = _normalize_brand(product.brand)
        product_type = _detect_product_type(product.title, product.category)
        normalized_name = _normalize_title(product.title)
        model_number = _normalize_model_number(product.model_number)
        identity_key = _build_identity_key(brand, product_type, model_number, normalized_name)
        return ProductIdentity(
            brand=brand,
            normalized_name=normalized_name,
            product_type=product_type,
            model_number=model_number,
            identity_key=identity_key,
        )


def _normalize_brand(raw_brand: str) -> str:
    brand = raw_brand.strip()
    if not brand:
        return ""
    if brand.upper() == brand and len(brand) > 1:
        return brand.title()
    return brand


def _normalize_model_number(raw_model_number: str | None) -> str | None:
    if raw_model_number is None:
        return None
    model_number = raw_model_number.strip()
    return model_number or None


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
    filtered = [token for token in tokens if token and token.lower() not in IDENTITY_NOISE_WORDS]
    return " ".join(filtered)


def _normalize_title(title: str) -> str:
    cleaned = _strip_noise_words(title)
    return " ".join(cleaned.lower().split())


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", value.lower())
    tokens = [token for token in cleaned.split() if token]
    return "_".join(tokens)


def _build_identity_key(
    brand: str,
    product_type: str,
    model_number: str | None,
    normalized_name: str,
) -> str:
    brand_slug = _slug(brand) or "unknown"
    if product_type:
        type_slug = _slug(product_type)
        key = f"{brand_slug}_{type_slug}"
    else:
        name_slug = _slug(normalized_name) or "unknown"
        key = f"{brand_slug}_{name_slug}"

    if model_number:
        model_slug = re.sub(r"[^\w]", "", model_number.lower())
        if model_slug:
            key = f"{key}_{model_slug}"

    return key
