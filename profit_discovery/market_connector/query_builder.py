"""Domestic market query generation from supplier products."""

from __future__ import annotations

from supplier.models import SupplierProduct

from profit_discovery.market_connector.models import MarketSearchRequest


def build_market_query(product: SupplierProduct) -> str:
    """
    Build a domestic market search query from supplier identity fields.

    Uses brand, title, and model number only. Does not include currency,
    purchase price, or supplier name.
    """
    brand = _normalize_text(product.brand)
    title = _normalize_text(product.title)

    parts: list[str] = []
    if brand:
        parts.append(brand)

    if title:
        if brand and title.lower().startswith(brand.lower()):
            remainder = title[len(brand) :].strip()
        elif title.lower() != brand.lower():
            remainder = title
        else:
            remainder = ""

        if remainder:
            words = remainder.split()
            if len(words) <= 2:
                parts.append(remainder)
            else:
                product_term = _extract_primary_product_term(remainder)
                if product_term:
                    parts.append(product_term)

    return " ".join(part for part in parts if part)


def _extract_primary_product_term(title: str) -> str:
    lowered = title.lower()
    for term in ("wallet", "bag", "flap", "tote", "shoulder"):
        if term in lowered:
            return term.capitalize() if term == "wallet" else term
    return " ".join(title.split()[:2])


def build_market_search_request(product: SupplierProduct) -> MarketSearchRequest:
    """Build a structured domestic market search request from a supplier product."""
    matched_keyword = build_market_query(product)
    keywords = tuple(token for token in matched_keyword.split() if token)
    if product.model_number:
        keywords = (*keywords, product.model_number)
    return MarketSearchRequest(
        supplier_name=product.supplier_name,
        product_name=product.title,
        brand=product.brand,
        model_number=product.model_number,
        keywords=keywords,
        metadata={
            "external_id": product.external_id,
            "category": product.category,
        },
    )


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().split())
