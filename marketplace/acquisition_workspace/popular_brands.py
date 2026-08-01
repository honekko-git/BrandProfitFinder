"""Popular-brand catalog for Fashionphile bulk acquisition (data-driven)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BRANDS_PATH = (
    Path(__file__).resolve().parents[2] / "chrome_extension" / "data" / "popular_brands.json"
)


@dataclass(frozen=True, slots=True)
class PopularBrand:
    canonical_brand: str
    display_name: str
    fashionphile_search_term: str
    fashionphile_search_url: str
    enabled: bool = True


def load_popular_brands(path: Path | str | None = None) -> tuple[PopularBrand, ...]:
    """Load enabled popular brands from external JSON (no brand if/else logic)."""
    target = Path(path) if path is not None else DEFAULT_BRANDS_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    brands = payload.get("brands")
    if not isinstance(brands, list):
        raise ValueError("popular_brands.json must contain a brands list")
    out: list[PopularBrand] = []
    for raw in brands:
        if not isinstance(raw, dict):
            continue
        if not bool(raw.get("enabled", True)):
            continue
        url = str(raw.get("fashionphile_search_url") or "").strip()
        canonical = str(raw.get("canonical_brand") or "").strip()
        if not url or not canonical:
            continue
        out.append(
            PopularBrand(
                canonical_brand=canonical,
                display_name=str(raw.get("display_name") or canonical).strip() or canonical,
                fashionphile_search_term=str(
                    raw.get("fashionphile_search_term") or canonical
                ).strip()
                or canonical,
                fashionphile_search_url=url,
                enabled=True,
            )
        )
    return tuple(out)


def filter_popular_brands(
    brands: tuple[PopularBrand, ...] | list[PopularBrand],
    query: str,
) -> tuple[PopularBrand, ...]:
    """Case-insensitive display/canonical filter for the popup search box."""
    needle = (query or "").strip().lower()
    if not needle:
        return tuple(brands)
    return tuple(
        item
        for item in brands
        if needle in item.display_name.lower()
        or needle in item.canonical_brand.lower()
        or needle in item.fashionphile_search_term.lower()
    )


def resolve_selected_brands(
    brands: tuple[PopularBrand, ...] | list[PopularBrand],
    selected_canonicals: list[str],
) -> tuple[PopularBrand, ...]:
    """Keep caller selection order; drop unknown/disabled brands."""
    by_name = {item.canonical_brand: item for item in brands}
    out: list[PopularBrand] = []
    seen: set[str] = set()
    for name in selected_canonicals:
        key = str(name or "").strip()
        if not key or key in seen:
            continue
        brand = by_name.get(key)
        if brand is None:
            continue
        seen.add(key)
        out.append(brand)
    return tuple(out)


def search_url_for_brand(brand: PopularBrand) -> str:
    """Return the configured public Fashionphile search URL (data-driven)."""
    return brand.fashionphile_search_url
