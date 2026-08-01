"""Deterministic handbag model-family identity for query + matching.

Brand/model knowledge lives in external dictionaries under
``model_dictionaries/``. This module is marketplace-neutral and must not
grow brand-specific if/else branches when new brands are added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.model_dictionaries import (
    ModelDictionaryBundle,
    ModelFamilyDefinition,
    brand_ja,
    families_for_brand,
    load_model_dictionaries,
)

# Backward-compatible family ID constants (values come from dictionaries).
FAMILY_CLASSIC_FLAP = "Classic Flap"
FAMILY_BOY = "Boy"
FAMILY_GABRIELLE = "Gabrielle"
FAMILY_CHANEL_19 = "Chanel 19"
FAMILY_COCO_HANDLE = "Coco Handle"
FAMILY_TRIPLE_COCO = "Triple Coco"
FAMILY_WALLET_ON_CHAIN = "Wallet On Chain"
FAMILY_VANITY = "Vanity"
FAMILY_TOTE = "Tote"
FAMILY_UNKNOWN = ""

FAMILY_SPEEDY = "Speedy"
FAMILY_NEVERFULL = "Neverfull"
FAMILY_ALMA = "Alma"
FAMILY_KEEPALL = "Keepall"
FAMILY_KELLY = "Kelly"
FAMILY_BIRKIN = "Birkin"
FAMILY_PICOTIN = "Picotin"
FAMILY_DIONYSUS = "Dionysus"
FAMILY_MARMONT = "Marmont"
FAMILY_JACKIE = "Jackie"
FAMILY_RE_EDITION = "Re-Edition"
FAMILY_GALLERIA = "Galleria"
FAMILY_CLEO = "Cleo"

STRUCTURAL_DOUBLE_FLAP = "Double Flap"
STRUCTURAL_SINGLE_FLAP = "Single Flap"

MAX_BAG_MODEL_QUERIES = 4


@dataclass(frozen=True, slots=True)
class HandbagModelIdentity:
    """Deterministic handbag identity signals used for query + matching."""

    brand: str
    model_family: str
    structural_modifier: str
    size: str
    material: str
    category: str
    distinct_family: str = ""
    positive_family_evidence: bool = False
    aliases_matched: tuple[str, ...] = ()

    @property
    def has_known_model_family(self) -> bool:
        return bool(self.model_family)

    @property
    def has_distinct_model_family(self) -> bool:
        """True when family is specific (not generic Tote/Bag/etc.)."""
        from marketplace.browser_acquisition.product_identity import is_generic_model_family

        return bool(self.model_family) and not is_generic_model_family(self.model_family)


def extract_handbag_model_identity(
    *,
    title: str,
    brand: str = "",
    category: str = "",
    dictionaries: ModelDictionaryBundle | None = None,
) -> HandbagModelIdentity:
    """Extract minimal handbag identity from a title via dictionary lookup."""
    bundle = dictionaries or load_model_dictionaries()
    normalized = _fold(title)
    brand_key = (brand or "").strip()
    material = detect_luxury_material(title).value
    if material == "Unknown":
        material = ""

    family_id, aliases, runner_up = _detect_model_family(
        normalized,
        brand=brand_key,
        dictionaries=bundle,
    )
    structural = _detect_structural(normalized, dictionaries=bundle)
    size = _detect_size(normalized, family_id=family_id, dictionaries=bundle)
    cat = _normalize_bag_category(category, normalized)

    if runner_up and not family_id:
        return HandbagModelIdentity(
            brand=brand_key,
            model_family="",
            structural_modifier=structural,
            size=size,
            material=material,
            category=cat,
            distinct_family=runner_up,
            positive_family_evidence=False,
            aliases_matched=(),
        )

    return HandbagModelIdentity(
        brand=brand_key,
        model_family=family_id,
        structural_modifier=structural,
        size=size,
        material=material,
        category=cat,
        distinct_family=runner_up if runner_up != family_id else "",
        positive_family_evidence=bool(family_id),
        aliases_matched=aliases,
    )


def build_bag_model_queries(
    identity: HandbagModelIdentity,
    *,
    brand: str = "",
    dictionaries: ModelDictionaryBundle | None = None,
) -> list[str]:
    """Build model-first domestic queries from dictionary query variants.

    Never brand+Bag alone when a model family is known.
    """
    bundle = dictionaries or load_model_dictionaries()
    brand_key = (identity.brand or brand or "").strip()
    ja_brand = brand_ja(brand_key, dictionaries=bundle)
    en_brand = brand_key.title() if brand_key else ""
    if not identity.model_family:
        return []

    family = _family_by_id(identity.model_family, dictionaries=bundle)
    structural_ja = _structural_ja(identity.structural_modifier, dictionaries=bundle)
    size_ja = _size_ja(identity.size, dictionaries=bundle)
    material_ja = _material_ja(identity.material, dictionaries=bundle)
    candidates: list[str] = []

    if family is not None:
        for variant in family.query_variants_ja:
            candidates.append(f"{ja_brand} {variant}".strip())
        primary = family.primary_ja or identity.model_family
        if structural_ja and size_ja:
            candidates.append(f"{ja_brand} {primary} {structural_ja} {size_ja}")
        if size_ja:
            candidates.append(f"{ja_brand} {primary} {size_ja}")
        if material_ja:
            # Prefer dictionary material query aliases when present (e.g. Patent → エナメル).
            material_aliases = bundle.material_query_aliases_ja.get(identity.material, (material_ja,))
            for alias in material_aliases[:2]:
                candidates.append(f"{ja_brand} {primary} {alias}")
        for variant in family.query_variants_en:
            candidates.append(
                " ".join(
                    part
                    for part in [en_brand, variant, identity.structural_modifier, identity.size]
                    if part
                )
            )
            candidates.append(f"{en_brand} {variant}".strip())
    else:
        # Unknown dictionary row: still emit brand + family name queries.
        candidates.extend(
            [
                " ".join(part for part in [ja_brand, identity.model_family, structural_ja, size_ja] if part),
                " ".join(part for part in [ja_brand, identity.model_family, size_ja] if part),
                " ".join(part for part in [en_brand, identity.model_family, identity.size] if part),
            ]
        )

    seen: set[str] = set()
    out: list[str] = []
    for query in candidates:
        normalized = re.sub(r"\s+", " ", query.strip())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= MAX_BAG_MODEL_QUERIES:
            break
    return out


def model_families_compatible(purchase: HandbagModelIdentity, sample: HandbagModelIdentity) -> tuple[bool, str]:
    """Return (ok, reason_code). Hard-fail conflicting known families."""
    if not purchase.has_known_model_family:
        return True, "MODEL_FAMILY_UNKNOWN"

    if sample.distinct_family and sample.distinct_family != purchase.model_family:
        return False, "DISTINCT_PRODUCT_FAMILY"

    if sample.has_known_model_family and sample.model_family != purchase.model_family:
        return False, "MODEL_FAMILY_CONFLICT"

    # Generic tote guard: tote category without positive family evidence is not a same-model match.
    if sample.category == "Tote" and not sample.positive_family_evidence:
        return False, "DISTINCT_PRODUCT_FAMILY"

    if not sample.positive_family_evidence:
        return False, "GENERIC_SAME_BRAND_INSUFFICIENT"

    return True, "MODEL_FAMILY_MATCH"


def _detect_model_family(
    normalized: str,
    *,
    brand: str,
    dictionaries: ModelDictionaryBundle,
) -> tuple[str, tuple[str, ...], str]:
    """Detect best model family via dictionary aliases.

    Strong aliases beat weak aliases when multiple families hit the same title
    (e.g. Boy + quilt token vs Classic Flap weak マトラッセ).
    """
    candidates = families_for_brand(brand, dictionaries=dictionaries)
    scored: list[tuple[int, int, str, tuple[str, ...]]] = []
    # score_key: (is_strong, max_alias_len, family_id, matched_aliases)
    for family in candidates:
        strong_matched = tuple(a for a in family.aliases if a and a in normalized)
        weak_matched = tuple(a for a in family.weak_aliases if a and a in normalized)
        if not strong_matched and not weak_matched:
            continue
        if strong_matched:
            scored.append((1, max(len(a) for a in strong_matched), family.id, strong_matched + weak_matched))
        else:
            scored.append((0, max(len(a) for a in weak_matched), family.id, weak_matched))

    if not scored:
        return "", (), ""

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    best_strong, best_len, best_id, best_aliases = scored[0]
    runner_up = ""
    for is_strong, _alias_len, family_id, _aliases in scored[1:]:
        if family_id != best_id:
            # A strong hit from another family is a distinct competing family.
            if is_strong or best_strong == 0:
                runner_up = family_id
            break

    # If the best hit is only weak and a strong competing family exists, prefer the strong family.
    if best_strong == 0:
        for is_strong, _alias_len, family_id, aliases in scored:
            if is_strong and family_id != best_id:
                return family_id, aliases, best_id
    return best_id, best_aliases, runner_up


def _family_by_id(family_id: str, *, dictionaries: ModelDictionaryBundle) -> ModelFamilyDefinition | None:
    for family in dictionaries.families:
        if family.id == family_id:
            return family
    return None


def _detect_structural(normalized: str, *, dictionaries: ModelDictionaryBundle) -> str:
    best_id = ""
    best_len = 0
    for structure in dictionaries.structures:
        for alias in structure.aliases:
            if alias and alias in normalized and len(alias) > best_len:
                best_id = structure.id
                best_len = len(alias)
    return best_id


def _detect_size(
    normalized: str,
    *,
    family_id: str = "",
    dictionaries: ModelDictionaryBundle,
) -> str:
    # Family-specific size aliases first (Speedy 25, Kelly 28, etc.).
    family = _family_by_id(family_id, dictionaries=dictionaries) if family_id else None
    if family and family.size_aliases:
        best_id = ""
        best_len = 0
        for size_id, aliases in family.size_aliases.items():
            for alias in aliases:
                folded = alias.lower()
                if folded and folded in normalized and len(folded) > best_len:
                    best_id = size_id
                    best_len = len(folded)
        if best_id:
            return best_id

    for size in dictionaries.sizes:
        if any(alias in normalized for alias in size.aliases if alias):
            return size.id
    return ""


def _normalize_bag_category(category: str, normalized_title: str) -> str:
    cat = (category or "").strip()
    if "tote" in normalized_title or "トート" in normalized_title:
        return "Tote"
    if cat.lower() in {"bag", "handbag"} or cat == "Bag":
        return "Bag"
    if cat.upper() in {"", "UNKNOWN", "BAG", "SHOULDER_BAG", "HANDBAG", "CROSSBODY", "CLUTCH"}:
        return "Bag"
    return cat or "Bag"


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("　", " ")).strip()


def _structural_ja(structural: str, *, dictionaries: ModelDictionaryBundle) -> str:
    for structure in dictionaries.structures:
        if structure.id == structural:
            # Prefer Japanese alias when available.
            for alias in structure.aliases:
                if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", alias):
                    return alias
            return structure.id
    return structural


def _size_ja(size: str, *, dictionaries: ModelDictionaryBundle) -> str:
    return dictionaries.size_ja.get(size, size)


def _material_ja(material: str, *, dictionaries: ModelDictionaryBundle) -> str:
    return dictionaries.materials_ja.get(material, material)


# ---------------------------------------------------------------------------
# Legacy aliases kept for older tests / docs (engine no longer branches on them)
# ---------------------------------------------------------------------------

CLASSIC_FLAP_ALIASES: tuple[str, ...] = ()
DISTINCT_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = ()
SIZE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = ()
DOUBLE_FLAP_ALIASES: tuple[str, ...] = ()


def _refresh_legacy_exports() -> None:
    """Populate module-level legacy tuples from dictionaries for import compatibility."""
    global CLASSIC_FLAP_ALIASES, DISTINCT_FAMILY_PATTERNS, SIZE_PATTERNS, DOUBLE_FLAP_ALIASES
    bundle = load_model_dictionaries()
    classic = _family_by_id(FAMILY_CLASSIC_FLAP, dictionaries=bundle)
    if classic is not None:
        CLASSIC_FLAP_ALIASES = classic.aliases + classic.weak_aliases
    DISTINCT_FAMILY_PATTERNS = tuple(
        (family.id, family.aliases + family.weak_aliases)
        for family in bundle.families
        if family.id != FAMILY_CLASSIC_FLAP
    )
    SIZE_PATTERNS = tuple((size.id, size.aliases) for size in bundle.sizes)
    double = next((s for s in bundle.structures if s.id == STRUCTURAL_DOUBLE_FLAP), None)
    DOUBLE_FLAP_ALIASES = double.aliases if double else ()


_refresh_legacy_exports()
