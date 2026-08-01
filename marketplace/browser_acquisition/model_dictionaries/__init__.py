"""Load brand-neutral handbag model dictionaries from JSON files.

Engine code must not hardcode brand/model knowledge — add entries here instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_DICT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class ModelFamilyDefinition:
    """One model-family row from the external dictionary."""

    id: str
    brand_keys: tuple[str, ...]
    primary_ja: str
    aliases: tuple[str, ...]
    weak_aliases: tuple[str, ...] = ()
    query_variants_ja: tuple[str, ...] = ()
    query_variants_en: tuple[str, ...] = ()
    size_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StructureDefinition:
    id: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SizeDefinition:
    id: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelDictionaryBundle:
    brands: dict[str, dict]
    families: tuple[ModelFamilyDefinition, ...]
    structures: tuple[StructureDefinition, ...]
    sizes: tuple[SizeDefinition, ...]
    size_ja: dict[str, str]
    materials_ja: dict[str, str]
    material_query_aliases_ja: dict[str, tuple[str, ...]]


def _load_json(name: str) -> dict:
    path = _DICT_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_model_dictionaries() -> ModelDictionaryBundle:
    """Load all model dictionaries (cached)."""
    brands_doc = _load_json("brands.json")
    families_doc = _load_json("families.json")
    structures_doc = _load_json("structures.json")
    sizes_doc = _load_json("sizes.json")
    materials_doc = _load_json("materials.json")

    families: list[ModelFamilyDefinition] = []
    for row in families_doc.get("families", []):
        size_aliases_raw = row.get("size_aliases") or {}
        size_aliases = {
            str(size_id): tuple(str(a) for a in aliases)
            for size_id, aliases in size_aliases_raw.items()
        }
        families.append(
            ModelFamilyDefinition(
                id=str(row["id"]),
                brand_keys=tuple(str(k).upper() for k in row.get("brand_keys") or ()),
                primary_ja=str(row.get("primary_ja") or row["id"]),
                aliases=tuple(str(a) for a in row.get("aliases") or ()),
                weak_aliases=tuple(str(a) for a in row.get("weak_aliases") or ()),
                query_variants_ja=tuple(str(a) for a in row.get("query_variants_ja") or ()),
                query_variants_en=tuple(str(a) for a in row.get("query_variants_en") or ()),
                size_aliases=size_aliases,
            )
        )

    structures = tuple(
        StructureDefinition(id=str(row["id"]), aliases=tuple(str(a) for a in row.get("aliases") or ()))
        for row in structures_doc.get("structures") or ()
    )
    sizes = tuple(
        SizeDefinition(id=str(row["id"]), aliases=tuple(str(a) for a in row.get("aliases") or ()))
        for row in sizes_doc.get("sizes") or ()
    )
    material_query = {
        str(k): tuple(str(a) for a in v)
        for k, v in (materials_doc.get("query_aliases_ja") or {}).items()
    }

    return ModelDictionaryBundle(
        brands={str(k).upper(): v for k, v in (brands_doc.get("brands") or {}).items()},
        families=tuple(families),
        structures=structures,
        sizes=sizes,
        size_ja={str(k): str(v) for k, v in (sizes_doc.get("size_ja") or {}).items()},
        materials_ja={str(k): str(v) for k, v in (materials_doc.get("materials_ja") or {}).items()},
        material_query_aliases_ja=material_query,
    )


def brand_ja(brand: str, *, dictionaries: ModelDictionaryBundle | None = None) -> str:
    """Resolve Japanese brand label from the brand dictionary."""
    bundle = dictionaries or load_model_dictionaries()
    key = _normalize_brand_key(brand, bundle)
    if key and key in bundle.brands:
        return str(bundle.brands[key].get("ja") or brand)
    return brand.strip()


def _normalize_brand_key(brand: str, bundle: ModelDictionaryBundle) -> str:
    raw = (brand or "").strip()
    if not raw:
        return ""
    upper = raw.upper().replace("È", "E")
    if upper in bundle.brands:
        return upper
    # Alias scan (e.g. LV → LOUIS VUITTON, Hermès → HERMES)
    folded = upper.lower()
    for key, meta in bundle.brands.items():
        aliases = [key.lower(), str(meta.get("ja") or "").lower()]
        aliases.extend(str(a).lower() for a in meta.get("aliases") or ())
        if folded in aliases or any(a and a in folded for a in aliases if len(a) > 2):
            return key
    return upper


def families_for_brand(brand: str, *, dictionaries: ModelDictionaryBundle | None = None) -> tuple[ModelFamilyDefinition, ...]:
    """Return families applicable to a brand (plus brandless families)."""
    bundle = dictionaries or load_model_dictionaries()
    key = _normalize_brand_key(brand, bundle)
    if not key:
        return bundle.families
    out: list[ModelFamilyDefinition] = []
    for family in bundle.families:
        if not family.brand_keys:
            out.append(family)
            continue
        if key in family.brand_keys:
            out.append(family)
            continue
        # Allow short keys like LV matching LOUIS VUITTON families.
        if any(bk in key or key in bk for bk in family.brand_keys):
            out.append(family)
    return tuple(out)
