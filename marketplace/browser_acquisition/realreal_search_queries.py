"""Search query generation for The RealReal overseas acquisition."""

from __future__ import annotations

import re

from marketplace.browser_acquisition.listing_identity import ListingIdentity, extract_listing_identity

MAX_SEARCH_QUERIES = 3


def build_realreal_search_queries(*, title: str, brand: str = "", category: str = "") -> list[str]:
    """Build up to three The RealReal search queries from listing fields."""
    identity = extract_listing_identity(title=title, brand=brand, category=category)
    return build_realreal_identity_queries(identity=identity, title=title, brand=brand, category=category)


def build_realreal_identity_queries(
    *,
    identity: ListingIdentity,
    title: str = "",
    brand: str = "",
    category: str = "",
) -> list[str]:
    """Build The RealReal queries from normalized listing identity.

    Priority: model number, brand, product line/family, category, material, color.
    Title only as fallback.
    """
    queries: list[str] = []
    brand_key = identity.brand or (brand or "").strip().upper()
    en_brand = brand_key.title() if brand_key else (brand or "").strip()
    cat = identity.category if identity.category not in {"", "UNKNOWN"} else (category or "")
    material = identity.material if identity.material not in {"", "UNKNOWN"} else ""
    color = identity.color or ""
    family = " ".join(identity.model_family_tokens[:3]) if identity.model_family_tokens else ""

    for model in identity.model_numbers[:2]:
        queries.append(f"{en_brand} {model}".strip())
        queries.append(model)

    if en_brand and family:
        queries.append(f"{en_brand} {family}".strip())
    queries.append(
        " ".join(
            part
            for part in [
                en_brand,
                cat.title() if cat else "",
                material.title() if material else "",
                color.title() if color else "",
            ]
            if part
        )
    )
    queries.append(
        " ".join(
            part
            for part in [en_brand, family or (cat.title() if cat else ""), material.title() if material else ""]
            if part
        )
    )

    if len([q for q in queries if _normalize_query(q)]) < MAX_SEARCH_QUERIES:
        queries.append(_title_fallback(title or identity.cleaned_title, brand=brand or identity.brand))

    seen: set[str] = set()
    out: list[str] = []
    for query in queries:
        normalized = _normalize_query(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= MAX_SEARCH_QUERIES:
            break
    return out


def _title_fallback(title: str, *, brand: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", f"{title} {brand}".lower()))
    noise = {
        "therealreal",
        "realreal",
        "authenticated",
        "authentic",
        "excellent",
        "very",
        "good",
        "condition",
        "used",
        "vintage",
        "sale",
        "off",
        "was",
        "now",
    }
    filtered = [token for token in sorted(tokens) if token not in noise and len(token) > 1]
    return " ".join(filtered[:8])


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())
