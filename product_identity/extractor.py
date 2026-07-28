"""Extract normalized identity profiles from domain models."""

from __future__ import annotations

from models.marketplace_listing import MarketplaceListing
from models.product import Product
from product_identity.enums import (
    BroadCategory,
    IdentifierScope,
    IdentifierSourceQuality,
    IdentifierType,
)
from product_identity.identifiers import build_identifier
from product_identity.models import NormalizedIdentifier, ProductIdentityProfile
from product_identity.normalization import normalize_brand, normalize_code, normalize_color, normalize_text


def extract_from_product(product: Product) -> ProductIdentityProfile:
    """Build a profile from an overseas Product without mutating it."""
    warnings: list[str] = []
    identifiers: list[NormalizedIdentifier] = []
    source_fields: list[str] = []

    brand = normalize_brand(product.brand)
    model_number = normalize_code(product.model)
    sku = normalize_code(product.sku)
    product_name = normalize_text(product.name)
    category = _resolve_category(product.category, product.name)

    if sku:
        jan_id = build_identifier(
            IdentifierType.JAN,
            product.sku,
            source_field="product.sku",
            scope=IdentifierScope.GLOBAL,
        )
        if jan_id is not None:
            identifiers.append(jan_id)
            source_fields.append("product.sku")

    if model_number:
        model_id = build_identifier(
            IdentifierType.MODEL_NUMBER,
            product.model,
            source_field="product.model",
            scope=IdentifierScope.MANUFACTURER,
        )
        if model_id is not None:
            identifiers.append(model_id)
            source_fields.append("product.model")

    if sku and not _looks_like_gtin(sku):
        sku_id = build_identifier(
            IdentifierType.SKU,
            product.sku,
            source_field="product.sku",
            scope=IdentifierScope.MARKETPLACE_LOCAL,
        )
        if sku_id is not None:
            identifiers.append(sku_id)

    return ProductIdentityProfile(
        marketplace="source_product",
        listing_id=product.sku or product.name,
        brand=brand,
        model_name=model_number,
        product_name=product_name,
        category=category,
        jan=_first_valid_normalized(identifiers, IdentifierType.JAN),
        model_number=model_number,
        structured_identifiers=tuple(identifiers),
        source_fields=tuple(_stable_unique(source_fields)),
        warnings=tuple(warnings),
    )


def extract_from_listing(listing: MarketplaceListing) -> ProductIdentityProfile:
    """Build a profile from a marketplace listing without mutating it."""
    warnings: list[str] = []
    identifiers: list[NormalizedIdentifier] = []
    source_fields: list[str] = []
    meta = listing.source_metadata or {}

    brand = normalize_brand(listing.brand)
    model_number = normalize_code(listing.model_number)
    style_code = normalize_code(meta.get("source_style_code"))
    reference_number = normalize_code(meta.get("source_reference_number"))
    product_name = normalize_text(listing.title)
    category = _resolve_category(str(meta.get("source_category") or ""), listing.title)

    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.JAN,
            listing.jan_code,
            source_field="listing.jan_code",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.GLOBAL,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.JAN,
            meta.get("source_jan"),
            source_field="metadata.source_jan",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.GLOBAL,
            source_quality=IdentifierSourceQuality.METADATA,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.GTIN,
            meta.get("source_gtin"),
            source_field="metadata.source_gtin",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.GLOBAL,
            source_quality=IdentifierSourceQuality.METADATA,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.MODEL_NUMBER,
            listing.model_number,
            source_field="listing.model_number",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.MANUFACTURER,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.STYLE_CODE,
            style_code,
            source_field="metadata.source_style_code",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.MANUFACTURER,
            source_quality=IdentifierSourceQuality.METADATA if style_code else IdentifierSourceQuality.EXPLICIT,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.REFERENCE_NUMBER,
            reference_number,
            source_field="metadata.source_reference_number",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.MANUFACTURER,
            source_quality=IdentifierSourceQuality.METADATA,
        ),
    )
    _add_identifier(
        identifiers,
        source_fields,
        build_identifier(
            IdentifierType.SKU,
            listing.sku,
            source_field="listing.sku",
            source_marketplace=listing.marketplace_name,
            scope=IdentifierScope.MARKETPLACE_LOCAL,
        ),
    )

    for item in identifiers:
        if item.normalized_value is None and item.original_value:
            warnings.append(f"malformed identifier in {item.source_field}")

    color = normalize_color(meta.get("source_color") or _extract_color_from_title(listing.title))
    size_value = normalize_code(meta.get("source_size"))
    size_system = normalize_code(meta.get("source_size_system"))

    return ProductIdentityProfile(
        marketplace=listing.marketplace_name,
        listing_id=listing.listing_id,
        brand=brand,
        model_name=model_number or style_code,
        product_name=product_name,
        category=category,
        jan=_first_valid_normalized(identifiers, IdentifierType.JAN),
        gtin=_first_valid_normalized(identifiers, IdentifierType.GTIN),
        style_code=style_code,
        model_number=model_number,
        reference_number=reference_number,
        color=color,
        size_value=size_value,
        size_system=size_system,
        variant=normalize_text(meta.get("source_variant")),
        condition=normalize_text(listing.condition),
        structured_identifiers=tuple(identifiers),
        source_fields=tuple(_stable_unique(source_fields)),
        warnings=tuple(_stable_unique(warnings)),
    )


def _add_identifier(
    identifiers: list[NormalizedIdentifier],
    source_fields: list[str],
    item: NormalizedIdentifier | None,
) -> None:
    if item is None:
        return
    identifiers.append(item)
    source_fields.append(item.source_field)


def _missing_identifier() -> NormalizedIdentifier:
    raise RuntimeError("unreachable")


def _looks_like_gtin(value: str) -> bool:
    digits = "".join(ch for ch in value if ch.isdigit())
    return len(digits) in {8, 12, 13, 14}


def _first_valid_normalized(
    identifiers: list[NormalizedIdentifier],
    identifier_type: IdentifierType,
) -> str | None:
    for item in identifiers:
        if item.identifier_type == identifier_type and item.is_valid and item.normalized_value:
            return item.normalized_value
    return None


def _resolve_category(raw_category: str, title: str) -> BroadCategory:
    text = f"{raw_category} {title}".lower()
    if any(token in text for token in ("shoe", "sneaker", "loafer", "boot")):
        return BroadCategory.FOOTWEAR
    if any(token in text for token in ("bag", "handbag", "marmont")):
        return BroadCategory.HANDBAG
    if any(token in text for token in ("watch", "chrono", "dial")):
        return BroadCategory.WATCH
    if any(token in text for token in ("cosmetic", "lipstick", "cream", "serum")):
        return BroadCategory.COSMETICS
    if any(token in text for token in ("shirt", "jacket", "apparel", "dress")):
        return BroadCategory.APPAREL
    return BroadCategory.GENERAL


def _extract_color_from_title(title: str) -> str | None:
    colors = {"black", "white", "red", "blue", "brown", "pink", "gold", "silver", "beige", "green"}
    tokens = set(normalize_text(title).split()) if normalize_text(title) else set()
    found = sorted(colors & tokens)
    return found[0] if found else None


def _stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
