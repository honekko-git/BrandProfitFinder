"""Select the best Yahoo comparable after deterministic matching."""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    NEAR_MISS_SCORE_THRESHOLD,
    ComparableEstimateResult,
    ComparableSampleDiagnostic,
)
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.models import AcquiredListing, YahooSoldSample


@dataclass(frozen=True, slots=True)
class YahooBestComparable:
    """Highest-quality accepted Yahoo comparable for detail display."""

    title: str
    price_jpy: int
    url: str
    matching_score: int
    matched_attributes: str
    condition: str = ""
    auction_status: str = ""
    seller: str = ""
    buyout_price_jpy: int | None = None
    bid_count: int | None = None
    image_url: str = ""
    identity_brand: str = ""
    identity_model: str = ""
    identity_category: str = ""
    identity_material: str = ""
    identity_color: str = ""
    identity_condition: str = ""


def select_best_yahoo_comparable(
    purchase: AcquiredListing,
    result: ComparableEstimateResult,
    *,
    min_score: int | None = None,
    candidate_samples: tuple[YahooSoldSample, ...] | list[YahooSoldSample] | None = None,
) -> YahooBestComparable | None:
    """Choose the best comparable using existing matching scores.

    Falls back to near-miss rows (hard gates passed, score at/above near-miss
    threshold) when nothing clears the accept threshold — used for open-auction
    detail/profit.
    """
    threshold = COMPARABLE_SCORE_THRESHOLD if min_score is None else min_score
    near_miss = NEAR_MISS_SCORE_THRESHOLD
    pool = [item for item in result.accepted_diagnostics if item.matching_score >= threshold]
    if not pool:
        pool = [
            item
            for item in result.rejected_diagnostics
            if item.matching_score >= near_miss
            and set(item.rejection_reasons) <= {"SCORE_BELOW_THRESHOLD"}
        ]
    if not pool:
        return None

    ranked = sorted(
        pool,
        key=lambda item: (
            item.matching_score,
            1 if item.detected_material not in {"", "Unknown", "UNKNOWN"} else 0,
            1 if item.detected_subtype not in {"", "UNKNOWN"} else 0,
        ),
        reverse=True,
    )
    best_diag = ranked[0]
    sample_pool = tuple(candidate_samples or ()) + tuple(result.matched_samples)
    sample = _find_sample(sample_pool, best_diag)
    purchase_identity = extract_listing_identity(
        title=purchase.title,
        brand=purchase.brand,
        category=purchase.category,
        condition=purchase.condition,
    )
    sample_identity = extract_listing_identity(
        title=best_diag.title,
        brand="",
        category="",
        condition=(sample.condition if sample is not None else ""),
    )
    attrs = _matched_attributes(purchase_identity, sample_identity, best_diag)
    price = sample.sold_price_jpy if sample is not None else best_diag.price_jpy
    url = sample.url if sample is not None else ""
    return YahooBestComparable(
        title=best_diag.title,
        price_jpy=int(price),
        url=url,
        matching_score=int(best_diag.matching_score),
        matched_attributes=attrs,
        condition=(sample.condition if sample is not None else "") or sample_identity.condition,
        auction_status=getattr(sample, "auction_status", "") if sample is not None else "",
        seller=getattr(sample, "seller", "") if sample is not None else "",
        buyout_price_jpy=getattr(sample, "buyout_price_jpy", None) if sample is not None else None,
        bid_count=getattr(sample, "bid_count", None) if sample is not None else None,
        image_url=getattr(sample, "image_url", "") if sample is not None else "",
        identity_brand=sample_identity.brand,
        identity_model=",".join(sample_identity.model_numbers),
        identity_category=sample_identity.category,
        identity_material=sample_identity.material,
        identity_color=sample_identity.color,
        identity_condition=sample_identity.condition,
    )


def _find_sample(
    samples: tuple[YahooSoldSample, ...],
    diagnostic: ComparableSampleDiagnostic,
) -> YahooSoldSample | None:
    for sample in samples:
        if sample.title == diagnostic.title and sample.sold_price_jpy == diagnostic.price_jpy:
            return sample
    for sample in samples:
        if sample.title == diagnostic.title:
            return sample
    return None


def _matched_attributes(purchase_identity, sample_identity, diagnostic: ComparableSampleDiagnostic) -> str:
    parts: list[str] = []
    purchase_models = set(purchase_identity.model_numbers)
    sample_models = set(sample_identity.model_numbers)
    overlap = purchase_models and sample_models and (purchase_models & sample_models)
    if overlap:
        parts.append("model:" + sorted(purchase_models & sample_models)[0])
    if (
        purchase_identity.material not in {"", "UNKNOWN"}
        and purchase_identity.material == sample_identity.material
    ):
        parts.append("material:" + purchase_identity.material)
    if (
        purchase_identity.category not in {"", "UNKNOWN"}
        and sample_identity.category not in {"", "UNKNOWN"}
    ):
        parts.append("category:" + (sample_identity.category or diagnostic.detected_subtype))
    if purchase_identity.color and purchase_identity.color == sample_identity.color:
        parts.append("color:" + purchase_identity.color)
    if diagnostic.model_tokens:
        parts.append("family:" + ",".join(list(diagnostic.model_tokens)[:3]))
    return "; ".join(parts) if parts else ("score:" + str(diagnostic.matching_score))
