"""Precision comparable matching for Yahoo sold samples."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from statistics import median

from marketplace.browser_acquisition.bag_model_family import (
    extract_handbag_model_identity,
    model_families_compatible,
)
from marketplace.browser_acquisition.listing_identity import (
    BAG_CATEGORIES,
    ListingIdentity,
    brand_aliases_for_match,
    categories_compatible,
    conditions_compatible,
    extract_listing_identity,
    materials_compatible as identity_materials_compatible,
    title_token_overlap,
)
from marketplace.browser_acquisition.comparable_quality import prefer_strong_matches_for_estimation
from marketplace.browser_acquisition.luxury_material import LuxuryMaterial, detect_luxury_material, materials_compatible
from marketplace.browser_acquisition.matching import compute_domestic_estimate, filter_matched_samples
from marketplace.browser_acquisition.matching_config import get_matching_config
from marketplace.browser_acquisition.models import AcquiredListing, ReliabilityLevel, YahooSoldSample
from marketplace.browser_acquisition.product_subtype import (
    WalletSubtype,
    detect_wallet_subtype,
    subtypes_compatible,
)

# Weights / thresholds / hard-reject flags loaded from data/matching_config.json.
_MATCHING_CONFIG = get_matching_config()
_WEIGHTS = _MATCHING_CONFIG.weights
_HARD_REJECT = _MATCHING_CONFIG.hard_reject
COMPARABLE_SCORE_THRESHOLD = _MATCHING_CONFIG.thresholds.accept_threshold
NEAR_MISS_SCORE_THRESHOLD = _MATCHING_CONFIG.thresholds.near_miss_threshold
CLASSIC_FAMILY_TOKENS = {"Classic", "Matelasse", "Flap"}

SCORE_MODEL_NUMBER = _WEIGHTS.model_number
SCORE_BRAND = _WEIGHTS.brand
SCORE_CATEGORY_EXACT = _WEIGHTS.category
SCORE_CATEGORY_RELATED = _WEIGHTS.category_related
SCORE_MATERIAL = _WEIGHTS.material
SCORE_COLOR = _WEIGHTS.color
SCORE_HARDWARE = _WEIGHTS.hardware
SCORE_MODEL_FAMILY = _WEIGHTS.model_family
SCORE_TITLE_TOKEN = _WEIGHTS.title_token
SCORE_TITLE_CAP = _WEIGHTS.title_similarity
SCORE_CONDITION = _WEIGHTS.condition

GENERIC_TOKENS = {
    "chanel",
    "wallet",
    "財布",
    "ウォレット",
    "black",
    "黒",
    "used",
    "シャネル",
    "brand",
    "luxury",
    "louis",
    "vuitton",
    "バッグ",
    "bag",
}

MODEL_TOKEN_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Classic", ("classic", "クラシック")),
    ("Boy", ("boy chanel", "boy", "ボーイ")),
    ("Cambon", ("cambon", "カンボン")),
    ("Matelasse", ("matelasse", "matelassé", "マトラッセ")),
    ("Coco Mark", ("coco mark", "coco", "ココマーク", "ココ")),
    ("Zip Around", ("zip around", "zip-around", "zip around wallet", "ラウンドファスナー")),
    ("Flap", ("flap", "フラップ")),
)

HARD_EXCLUSION_PATTERNS = (
    "coin case",
    "coin purse",
    "コインケース",
    "小銭入れ",
    "card case",
    "card holder",
    "カードケース",
    "名刺入れ",
    "key case",
    "キーケース",
    "パスケース",
    "box only",
    "箱のみ",
    "保存袋のみ",
    "空箱",
    "parts only",
    "部品取り",
    "部品のみ",
    "ジャンク",
    "訳あり",
    "repair",
    "修理用",
    "replica",
    "fake",
    "strap only",
    "accessory only",
    "dust bag only",
)


class RejectionReason(StrEnum):
    """Primary rejection reason for one Yahoo sample."""

    SUBTYPE_MISMATCH = "SUBTYPE_MISMATCH"
    ACCESSORY_ONLY = "ACCESSORY_ONLY"
    MATERIAL_MISMATCH = "MATERIAL_MISMATCH"
    MODEL_SIMILARITY_LOW = "MODEL_SIMILARITY_LOW"
    MODEL_NUMBER_MISMATCH = "MODEL_NUMBER_MISMATCH"
    HARD_EXCLUSION = "HARD_EXCLUSION"
    SCORE_BELOW_THRESHOLD = "SCORE_BELOW_THRESHOLD"
    BRAND_MISMATCH = "BRAND_MISMATCH"
    CATEGORY_MISMATCH = "CATEGORY_MISMATCH"
    MODEL_FAMILY_MATCH = "MODEL_FAMILY_MATCH"
    MODEL_FAMILY_UNKNOWN = "MODEL_FAMILY_UNKNOWN"
    MODEL_FAMILY_CONFLICT = "MODEL_FAMILY_CONFLICT"
    DISTINCT_PRODUCT_FAMILY = "DISTINCT_PRODUCT_FAMILY"
    STRUCTURAL_MODIFIER_CONFLICT = "STRUCTURAL_MODIFIER_CONFLICT"
    SIZE_CONFLICT = "SIZE_CONFLICT"
    MATERIAL_MATCH_INSUFFICIENT = "MATERIAL_MATCH_INSUFFICIENT"
    GENERIC_SAME_BRAND_INSUFFICIENT = "GENERIC_SAME_BRAND_INSUFFICIENT"
    QUERY_MODEL_EVIDENCE_MISSING = "QUERY_MODEL_EVIDENCE_MISSING"


@dataclass(frozen=True, slots=True)
class ComparableSampleDiagnostic:
    """Diagnostics for one Yahoo sold sample evaluation."""

    title: str
    price_jpy: int
    detected_subtype: str
    detected_material: str
    model_tokens: tuple[str, ...]
    matching_score: int
    accepted: bool
    rejection_reasons: tuple[str, ...]
    model_family: str = ""
    structural_modifier: str = ""
    size: str = ""
    category_family: str = ""
    score_components: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class ComparableEstimateResult:
    """Comparable domestic estimate with diagnostics."""

    sample_count: int
    raw_sample_count: int
    rejected_count: int
    minimum_jpy: int
    maximum_jpy: int
    average_jpy: Decimal
    median_jpy: Decimal
    trimmed_median_jpy: Decimal | None
    trimmed_average_jpy: Decimal | None
    reliability: ReliabilityLevel
    matched_samples: tuple[YahooSoldSample, ...]
    accepted_diagnostics: tuple[ComparableSampleDiagnostic, ...]
    rejected_diagnostics: tuple[ComparableSampleDiagnostic, ...]
    purchase_subtype: str
    purchase_material: str
    purchase_model_tokens: tuple[str, ...]
    legacy_median_jpy: Decimal
    outlier_exclusions: tuple[str, ...]
    data_warning: str = ""


def evaluate_comparables(
    purchase: AcquiredListing,
    samples: list[YahooSoldSample],
    *,
    purchase_price_jpy: Decimal | None = None,
) -> ComparableEstimateResult:
    """Evaluate Yahoo samples and build a comparable-only domestic estimate."""
    purchase_subtype = detect_wallet_subtype(purchase.title)
    purchase_material = detect_luxury_material(purchase.title)
    purchase_model_tokens = detect_model_tokens(purchase.title)
    purchase_identity = extract_listing_identity(
        title=purchase.title,
        brand=purchase.brand,
        category=purchase.category,
        condition=purchase.condition,
        model_family_tokens=purchase_model_tokens,
    )

    accepted_rows: list[tuple[YahooSoldSample, ComparableSampleDiagnostic]] = []
    rejected: list[ComparableSampleDiagnostic] = []

    for sample in samples:
        diagnostic = _evaluate_sample(
            purchase=purchase,
            sample=sample,
            purchase_subtype=purchase_subtype,
            purchase_material=purchase_material,
            purchase_model_tokens=purchase_model_tokens,
            purchase_identity=purchase_identity,
        )
        if diagnostic.accepted:
            accepted_rows.append((sample, diagnostic))
        else:
            rejected.append(diagnostic)

    # Prefer strong model matches before IQR so cheap category comps cannot dominate.
    accepted_rows, _prefer_counts = prefer_strong_matches_for_estimation(accepted_rows)
    accepted_samples = [sample for sample, _ in accepted_rows]
    prices = [sample.sold_price_jpy for sample in accepted_samples]
    filtered_prices, outlier_notes = _remove_iqr_outliers(prices)
    filtered_set = set(filtered_prices)

    comparable_median = Decimal(str(int(median(filtered_prices)))) if filtered_prices else Decimal("0")
    legacy_matched = filter_matched_samples(purchase, samples, min_score=60)
    legacy_estimate = compute_domestic_estimate(legacy_matched)
    legacy_median = legacy_estimate.median_jpy
    data_warning = ""
    if purchase_price_jpy is not None and comparable_median > 0:
        threshold = purchase_price_jpy * Decimal("0.30")
        if comparable_median < threshold:
            data_warning = "COMPARABLE_DATA_SUSPECT"

    reliability = _reliability(len(filtered_prices))
    trimmed_median = _trimmed_median(filtered_prices)
    trimmed_average = _trimmed_average(filtered_prices)
    final_samples = tuple(
        sample for sample in accepted_samples if sample.sold_price_jpy in filtered_set
    ) if filtered_set else tuple(accepted_samples)

    return ComparableEstimateResult(
        sample_count=len(filtered_prices),
        raw_sample_count=len(samples),
        rejected_count=len(rejected),
        minimum_jpy=min(filtered_prices) if filtered_prices else 0,
        maximum_jpy=max(filtered_prices) if filtered_prices else 0,
        average_jpy=Decimal(str(round(sum(filtered_prices) / len(filtered_prices)))) if filtered_prices else Decimal("0"),
        median_jpy=comparable_median,
        trimmed_median_jpy=trimmed_median,
        trimmed_average_jpy=trimmed_average,
        reliability=reliability,
        matched_samples=final_samples,
        accepted_diagnostics=tuple(item for _sample, item in accepted_rows if item.accepted),
        rejected_diagnostics=tuple(rejected),
        purchase_subtype=purchase_subtype.value,
        purchase_material=purchase_material.value,
        purchase_model_tokens=purchase_model_tokens,
        legacy_median_jpy=legacy_median,
        outlier_exclusions=tuple(outlier_notes),
        data_warning=data_warning,
    )


def detect_model_tokens(title: str) -> tuple[str, ...]:
    """Detect model/family tokens from title text."""
    from marketplace.browser_acquisition.product_identity import extract_collection, extract_size_token

    normalized = re.sub(r"\s+", " ", title.lower()).strip()
    found: list[str] = []
    collection = extract_collection(title)
    if collection:
        found.append(collection)
    for label, patterns in MODEL_TOKEN_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            found.append(label)
    bag_identity = extract_handbag_model_identity(title=title)
    if (
        bag_identity.model_family
        and bag_identity.model_family not in found
        and bag_identity.model_family.lower() not in {"tote", "bag", "handbag"}
    ):
        found.insert(0 if not collection else 1, bag_identity.model_family)
    if bag_identity.structural_modifier and bag_identity.structural_modifier not in found:
        found.append(bag_identity.structural_modifier)
    size = bag_identity.size or extract_size_token(title)
    if size and size not in found:
        found.append(size)
    # De-dupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for token in found:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(token)
    return tuple(ordered)


def format_comparable_diagnostics(result: ComparableEstimateResult) -> str:
    """Serialize comparable diagnostics for browser display."""
    payload = {
        "accepted": [
            {
                "title": item.title,
                "price_jpy": item.price_jpy,
                "subtype": item.detected_subtype,
                "material": item.detected_material,
                "model_tokens": list(item.model_tokens),
                "model_family": item.model_family,
                "structural_modifier": item.structural_modifier,
                "size": item.size,
                "category_family": item.category_family,
                "score_components": list(item.score_components),
                "score": item.matching_score,
            }
            for item in result.accepted_diagnostics
        ],
        "rejected": [
            {
                "title": item.title,
                "price_jpy": item.price_jpy,
                "subtype": item.detected_subtype,
                "material": item.detected_material,
                "model_tokens": list(item.model_tokens),
                "model_family": item.model_family,
                "structural_modifier": item.structural_modifier,
                "size": item.size,
                "category_family": item.category_family,
                "score_components": list(item.score_components),
                "score": item.matching_score,
                "reasons": list(item.rejection_reasons),
            }
            for item in result.rejected_diagnostics[:8]
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _evaluate_sample(
    *,
    purchase: AcquiredListing,
    sample: YahooSoldSample,
    purchase_subtype: WalletSubtype,
    purchase_material: LuxuryMaterial,
    purchase_model_tokens: tuple[str, ...],
    purchase_identity: ListingIdentity,
) -> ComparableSampleDiagnostic:
    sample_subtype = detect_wallet_subtype(sample.title)
    sample_material = detect_luxury_material(sample.title)
    sample_model_tokens = detect_model_tokens(sample.title)
    sample_identity = extract_listing_identity(
        title=sample.title,
        brand="",
        category="",
        condition=sample.condition,
        model_family_tokens=sample_model_tokens,
    )
    purchase_bag = extract_handbag_model_identity(
        title=purchase.title,
        brand=purchase.brand or purchase_identity.brand,
        category=purchase.category or purchase_identity.category,
    )
    sample_bag = extract_handbag_model_identity(
        title=sample.title,
        brand=purchase.brand or purchase_identity.brand,
        category=sample_identity.category,
    )
    reasons: list[str] = []

    # Priority 2 — Brand (hard gate)
    if not _brand_match(purchase.brand or purchase_identity.brand, sample.title):
        reasons.append(RejectionReason.BRAND_MISMATCH.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            0,
            False,
            reasons,
            sample_bag=sample_bag,
        )

    if _hard_exclusion_hit(sample.title, purchase_subtype, sample_subtype):
        reasons.append(RejectionReason.HARD_EXCLUSION.value)
        if sample_subtype in {WalletSubtype.COIN_CASE, WalletSubtype.CARD_HOLDER, WalletSubtype.KEY_CASE}:
            reasons.append(RejectionReason.ACCESSORY_ONLY.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            0,
            False,
            reasons,
            sample_bag=sample_bag,
        )

    # Priority 1 — Model number mismatch when both sides expose codes
    purchase_codes = set(purchase_identity.model_numbers)
    sample_codes = set(sample_identity.model_numbers)
    if (
        _HARD_REJECT.different_model_number
        and purchase_codes
        and sample_codes
        and purchase_codes.isdisjoint(sample_codes)
    ):
        reasons.append(RejectionReason.MODEL_NUMBER_MISMATCH.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            0,
            False,
            reasons,
            sample_bag=sample_bag,
        )

    # Priority 3 — Category / subtype
    if _HARD_REJECT.category_conflict and not categories_compatible(
        purchase_identity.category, sample_identity.category
    ):
        reasons.append(RejectionReason.CATEGORY_MISMATCH.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            0,
            False,
            reasons,
            sample_bag=sample_bag,
        )

    # Keep wallet subtype hard gate when both sides look like wallets
    if purchase_subtype != WalletSubtype.UNKNOWN and sample_subtype != WalletSubtype.UNKNOWN:
        if not subtypes_compatible(purchase_subtype, sample_subtype):
            reasons.append(RejectionReason.SUBTYPE_MISMATCH.value)
            return _diagnostic(
                sample,
                sample_subtype,
                sample_material,
                sample_model_tokens,
                0,
                False,
                reasons,
                sample_bag=sample_bag,
            )

    # Handbag model-family hard gates (known purchase family only)
    family_ok, family_reason = model_families_compatible(purchase_bag, sample_bag)
    if purchase_bag.has_known_model_family and not family_ok:
        reasons.append(family_reason)
        if family_reason == RejectionReason.GENERIC_SAME_BRAND_INSUFFICIENT.value:
            reasons.append(RejectionReason.MATERIAL_MATCH_INSUFFICIENT.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            0,
            False,
            reasons,
            sample_bag=sample_bag,
        )

    # Priority 4 — Material
    # Same known handbag model family: material mismatch is soft (no points), not a hard reject.
    # Threshold stays 70; model-family gates remain authoritative.
    material_soft_mismatch = False
    if _HARD_REJECT.material_conflict:
        material_ok = materials_compatible(purchase_material, sample_material) and identity_materials_compatible(
            purchase_identity.material, sample_identity.material
        )
        if not material_ok:
            if purchase_bag.has_known_model_family and family_ok:
                material_soft_mismatch = True
            else:
                reasons.append(RejectionReason.MATERIAL_MISMATCH.value)
                return _diagnostic(
                    sample,
                    sample_subtype,
                    sample_material,
                    sample_model_tokens,
                    0,
                    False,
                    reasons,
                    sample_bag=sample_bag,
                )

    score, components = _score_sample(
        purchase=purchase,
        sample=sample,
        purchase_identity=purchase_identity,
        sample_identity=sample_identity,
        purchase_subtype=purchase_subtype,
        sample_subtype=sample_subtype,
        purchase_model_tokens=purchase_model_tokens,
        sample_model_tokens=sample_model_tokens,
        purchase_bag=purchase_bag,
        sample_bag=sample_bag,
        skip_material_credit=material_soft_mismatch,
    )

    soft_notes: list[str] = []
    if material_soft_mismatch:
        soft_notes.append(RejectionReason.MATERIAL_MATCH_INSUFFICIENT.value)
    if (
        purchase_bag.structural_modifier
        and sample_bag.structural_modifier
        and purchase_bag.structural_modifier != sample_bag.structural_modifier
    ):
        soft_notes.append(RejectionReason.STRUCTURAL_MODIFIER_CONFLICT.value)
    if purchase_bag.size and sample_bag.size and purchase_bag.size != sample_bag.size:
        soft_notes.append(RejectionReason.SIZE_CONFLICT.value)

    if purchase_model_tokens and not set(purchase_model_tokens) & set(sample_model_tokens):
        # Soft token path only when handbag model family is unknown.
        if not purchase_bag.has_known_model_family:
            purchase_family = set(purchase_model_tokens) & CLASSIC_FAMILY_TOKENS
            sample_family = set(sample_model_tokens) & CLASSIC_FAMILY_TOKENS
            soft_family = bool(purchase_family and sample_family)
            if not soft_family and not (purchase_codes & sample_codes) and score < COMPARABLE_SCORE_THRESHOLD:
                soft_notes.append(RejectionReason.MODEL_SIMILARITY_LOW.value)

    if score < COMPARABLE_SCORE_THRESHOLD:
        reasons.extend(soft_notes)
        reasons.append(RejectionReason.SCORE_BELOW_THRESHOLD.value)
        return _diagnostic(
            sample,
            sample_subtype,
            sample_material,
            sample_model_tokens,
            score,
            False,
            reasons,
            sample_bag=sample_bag,
            score_components=components,
        )

    accept_reasons = [RejectionReason.MODEL_FAMILY_MATCH.value] if purchase_bag.has_known_model_family and family_ok else []
    accept_reasons.extend(soft_notes)
    return _diagnostic(
        sample,
        sample_subtype,
        sample_material,
        sample_model_tokens,
        score,
        True,
        accept_reasons,
        sample_bag=sample_bag,
        score_components=components,
    )


def _family_token_points(overlap_models: set[str]) -> int:
    """Score overlapping model/collection tokens; multi-word collections are strong."""
    if any((" " in token) or (len(token) >= 8) for token in overlap_models):
        return max(SCORE_MODEL_FAMILY, 40)
    return min(SCORE_MODEL_FAMILY, max(1, len(overlap_models)) * 12)


def _score_sample(
    *,
    purchase: AcquiredListing,
    sample: YahooSoldSample,
    purchase_identity: ListingIdentity,
    sample_identity: ListingIdentity,
    purchase_subtype: WalletSubtype,
    sample_subtype: WalletSubtype,
    purchase_model_tokens: tuple[str, ...],
    sample_model_tokens: tuple[str, ...],
    purchase_bag=None,
    sample_bag=None,
    skip_material_credit: bool = False,
) -> tuple[int, tuple[tuple[str, int], ...]]:
    """Score by matching priority: model number > family > category > material > ..."""
    components: list[tuple[str, int]] = []
    score = 0

    # Priority 1 — Model number
    purchase_codes = set(purchase_identity.model_numbers)
    sample_codes = set(sample_identity.model_numbers)
    if purchase_codes and sample_codes and purchase_codes & sample_codes:
        score += SCORE_MODEL_NUMBER
        components.append(("model_number", SCORE_MODEL_NUMBER))

    # Handbag model family (stronger than material when known; skip generic Tote/Bag)
    if purchase_bag is not None and sample_bag is not None and purchase_bag.has_known_model_family:
        from marketplace.browser_acquisition.product_identity import is_generic_model_family

        same_family = (
            sample_bag.positive_family_evidence
            and sample_bag.model_family == purchase_bag.model_family
        )
        if same_family and not is_generic_model_family(purchase_bag.model_family):
            family_points = max(SCORE_MODEL_FAMILY, 40)
            score += family_points
            components.append(("model_family", family_points))
            if (
                purchase_bag.structural_modifier
                and sample_bag.structural_modifier
                and purchase_bag.structural_modifier == sample_bag.structural_modifier
            ):
                score += 10
                components.append(("structural_modifier", 10))
            if purchase_bag.size and sample_bag.size and purchase_bag.size == sample_bag.size:
                score += 8
                components.append(("size", 8))
        else:
            # Generic taxonomy (Tote/Bag) or mismatched family: use collection/token overlap.
            overlap_models = set(purchase_model_tokens) & set(sample_model_tokens)
            if overlap_models:
                points = _family_token_points(overlap_models)
                score += points
                components.append(("model_family_tokens", points))
    else:
        overlap_models = set(purchase_model_tokens) & set(sample_model_tokens)
        if not overlap_models:
            purchase_family = set(purchase_model_tokens) & CLASSIC_FAMILY_TOKENS
            sample_family = set(sample_model_tokens) & CLASSIC_FAMILY_TOKENS
            # Do not treat Coco Mark alone as Classic Flap soft family.
            if purchase_family and sample_family:
                overlap_models = purchase_family & sample_family
        if overlap_models:
            points = _family_token_points(overlap_models)
            score += points
            components.append(("model_family_tokens", points))

    # Priority 3 — Category (lower weight; category-only must not reach HIGH alone)
    if (
        purchase_identity.category != "UNKNOWN"
        and purchase_identity.category == sample_identity.category
    ):
        score += SCORE_CATEGORY_EXACT
        components.append(("category_exact", SCORE_CATEGORY_EXACT))
    elif categories_compatible(purchase_identity.category, sample_identity.category):
        from marketplace.browser_acquisition.product_identity import is_generic_model_family

        if purchase_subtype == sample_subtype and purchase_subtype != WalletSubtype.UNKNOWN:
            score += SCORE_CATEGORY_EXACT
            components.append(("category_subtype", SCORE_CATEGORY_EXACT))
        elif (
            purchase_subtype in {WalletSubtype.BIFOLD_WALLET, WalletSubtype.COMPACT_WALLET}
            and sample_subtype in {WalletSubtype.BIFOLD_WALLET, WalletSubtype.COMPACT_WALLET}
        ):
            score += SCORE_CATEGORY_RELATED
            components.append(("category_related", SCORE_CATEGORY_RELATED))
        elif (
            purchase_bag is not None
            and sample_bag is not None
            and purchase_bag.has_known_model_family
            and sample_bag.positive_family_evidence
            and sample_bag.model_family == purchase_bag.model_family
            and not is_generic_model_family(purchase_bag.model_family)
            and purchase_identity.category in BAG_CATEGORIES
            and sample_identity.category in BAG_CATEGORIES
        ):
            # Same distinct model family within bag taxonomy.
            score += SCORE_CATEGORY_EXACT
            components.append(("category_same_model_bag", SCORE_CATEGORY_EXACT))
        elif purchase_identity.category != "UNKNOWN" and sample_identity.category != "UNKNOWN":
            if purchase_bag is not None and purchase_bag.has_known_model_family:
                if is_generic_model_family(purchase_bag.model_family):
                    points = min(15, SCORE_CATEGORY_RELATED)
                else:
                    points = min(15, SCORE_CATEGORY_RELATED)
            else:
                points = SCORE_CATEGORY_RELATED
            score += points
            components.append(("category_related", points))

    # Priority 4 — Material (secondary to model family; skipped on soft mismatch)
    if (
        not skip_material_credit
        and purchase_identity.material not in {"", "UNKNOWN"}
        and purchase_identity.material == sample_identity.material
    ):
        score += SCORE_MATERIAL
        components.append(("material", SCORE_MATERIAL))

    # Priority 5 — Color
    if purchase_identity.color and sample_identity.color and purchase_identity.color == sample_identity.color:
        score += SCORE_COLOR
        components.append(("color", SCORE_COLOR))

    # Priority 6 — Hardware
    if (
        purchase_identity.hardware
        and sample_identity.hardware
        and purchase_identity.hardware == sample_identity.hardware
    ):
        score += SCORE_HARDWARE
        components.append(("hardware", SCORE_HARDWARE))

    # Priority 7 — Title similarity
    overlap = title_token_overlap(purchase.title, sample.title, generic_tokens=GENERIC_TOKENS)
    title_points = min(SCORE_TITLE_CAP, overlap * SCORE_TITLE_TOKEN)
    if title_points:
        score += title_points
        components.append(("title_similarity", title_points))

    # Condition (soft)
    if conditions_compatible(purchase_identity.condition, sample_identity.condition):
        if purchase_identity.condition != "UNKNOWN" and sample_identity.condition != "UNKNOWN":
            score += SCORE_CONDITION
            components.append(("condition", SCORE_CONDITION))

    return min(100, score), tuple(components)


def _brand_match(purchase_brand: str, sample_title: str) -> bool:
    if not purchase_brand:
        return True
    normalized_title = sample_title.lower()
    aliases = brand_aliases_for_match(purchase_brand)
    if not aliases:
        brand_key = purchase_brand.strip().lower()
        aliases = (brand_key,)
    return any(alias in normalized_title or alias in sample_title for alias in aliases)


def _hard_exclusion_hit(title: str, purchase_subtype: WalletSubtype, sample_subtype: WalletSubtype) -> bool:
    normalized = title.lower()
    if purchase_subtype == sample_subtype:
        return False
    return any(pattern in normalized for pattern in HARD_EXCLUSION_PATTERNS)


def _diagnostic(
    sample: YahooSoldSample,
    subtype: WalletSubtype,
    material: LuxuryMaterial,
    model_tokens: tuple[str, ...],
    score: int,
    accepted: bool,
    reasons: list[str],
    *,
    sample_bag=None,
    score_components: tuple[tuple[str, int], ...] = (),
) -> ComparableSampleDiagnostic:
    return ComparableSampleDiagnostic(
        title=sample.title,
        price_jpy=sample.sold_price_jpy,
        detected_subtype=subtype.value,
        detected_material=material.value,
        model_tokens=model_tokens,
        matching_score=score,
        accepted=accepted,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        model_family=(sample_bag.model_family if sample_bag else "") or (
            sample_bag.distinct_family if sample_bag else ""
        ),
        structural_modifier=sample_bag.structural_modifier if sample_bag else "",
        size=sample_bag.size if sample_bag else "",
        category_family=sample_bag.category if sample_bag else "",
        score_components=score_components,
    )


def _remove_iqr_outliers(prices: list[int]) -> tuple[list[int], list[str]]:
    if len(prices) < 4:
        return prices, []
    sorted_prices = sorted(prices)
    q1 = sorted_prices[len(sorted_prices) // 4]
    q3 = sorted_prices[(len(sorted_prices) * 3) // 4]
    iqr = q3 - q1
    lower = q1 - int(iqr * 1.5)
    upper = q3 + int(iqr * 1.5)
    kept: list[int] = []
    notes: list[str] = []
    for price in sorted_prices:
        if price < lower or price > upper:
            notes.append(f"IQR outlier excluded: {price:,} JPY")
        else:
            kept.append(price)
    return kept or sorted_prices, notes


def _trimmed_median(prices: list[int]) -> Decimal | None:
    if len(prices) < 4:
        return None
    trimmed = prices[1:-1]
    if not trimmed:
        return None
    return Decimal(str(int(median(trimmed))))


def _trimmed_average(prices: list[int]) -> Decimal | None:
    if len(prices) < 4:
        return None
    trimmed = prices[1:-1]
    if not trimmed:
        return None
    return Decimal(str(round(sum(trimmed) / len(trimmed))))


def _reliability(count: int) -> ReliabilityLevel:
    if count >= 8:
        return ReliabilityLevel.HIGH
    if count >= 3:
        return ReliabilityLevel.MEDIUM
    return ReliabilityLevel.LOW
