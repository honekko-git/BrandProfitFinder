"""Search query generation for Vestiaire Collective overseas acquisition."""

from __future__ import annotations

import re

from marketplace.browser_acquisition.listing_identity import ListingIdentity, extract_listing_identity

MAX_SEARCH_QUERIES = 4

_NOISE = {
    "vestiaire",
    "vestiairecollective",
    "collective",
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
    "we",
    "love",
    "ships",
    "from",
}


def build_vestiaire_search_queries(*, title: str, brand: str = "", category: str = "") -> list[str]:
    """Build Vestiaire Collective search queries from listing fields."""
    identity = extract_listing_identity(title=title, brand=brand, category=category)
    return build_vestiaire_identity_queries(identity=identity, title=title, brand=brand, category=category)


def build_vestiaire_identity_queries(
    *,
    identity: ListingIdentity,
    title: str = "",
    brand: str = "",
    category: str = "",
) -> list[str]:
    """Ordered Vestiaire queries: model → brand+model → family → category → material/color → title.

    Priority:
    1. Model number
    2. Brand + model number
    3. Brand + product line / family
    4. Brand + family + category
    5. Brand + category + material
    6. Brand + category + color
    7. Cleaned title fallback
    """
    queries: list[str] = []
    brand_key = identity.brand or (brand or "").strip().upper()
    en_brand = brand_key.title() if brand_key else (brand or "").strip()
    cat = identity.category if identity.category not in {"", "UNKNOWN"} else (category or "")
    material = identity.material if identity.material not in {"", "UNKNOWN"} else ""
    color = identity.color or ""
    family = " ".join(identity.model_family_tokens[:3]) if identity.model_family_tokens else ""

    for model in identity.model_numbers[:2]:
        queries.append(model)
        queries.append(f"{en_brand} {model}".strip())

    if en_brand and family:
        queries.append(f"{en_brand} {family}".strip())
        if cat:
            queries.append(f"{en_brand} {family} {cat.title()}".strip())

    if en_brand and cat and material:
        queries.append(f"{en_brand} {cat.title()} {material.title()}".strip())
    if en_brand and cat and color:
        queries.append(f"{en_brand} {cat.title()} {color.title()}".strip())
    if en_brand and cat and not material and not color:
        queries.append(f"{en_brand} {cat.title()}".strip())

    queries.append(_title_fallback(title or identity.cleaned_title, brand=brand or identity.brand))

    seen: set[str] = set()
    out: list[str] = []
    for query in queries:
        normalized = _normalize_query(query)
        if not normalized or normalized in seen:
            continue
        # Avoid brand-only when stronger queries exist.
        if normalized.lower() == en_brand.lower() and len(out) > 0:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= MAX_SEARCH_QUERIES:
            break
    return out


def _title_fallback(title: str, *, brand: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9À-ÿ]+", f"{title} {brand}")
    filtered: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in _NOISE or len(key) <= 1 or key in seen:
            continue
        seen.add(key)
        filtered.append(token)
        if len(filtered) >= 8:
            break
    return " ".join(filtered)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())
