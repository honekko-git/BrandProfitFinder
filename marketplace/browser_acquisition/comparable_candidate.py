"""Marketplace-neutral comparable candidate selection.

Small internal representation so Yahoo, Mercari, and future marketplaces
share one collection-based best-comparable selector. Does not change
matching scores, thresholds, or profit logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    NEAR_MISS_SCORE_THRESHOLD,
)
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable

MATCH_STATUS_ACCEPTED = "accepted"
MATCH_STATUS_NEAR_MISS = "near_miss"
MATCH_STATUS_HARD_REJECTED = "hard_rejected"


@dataclass(frozen=True, slots=True)
class ComparableCandidate:
    """One marketplace-neutral comparable candidate for best-of selection."""

    marketplace: str
    title: str
    price_jpy: int
    listing_url: str
    condition: str
    matching_score: int
    matched_attributes: str
    match_status: str
    identity_material: str = ""
    identity_category: str = ""
    source: YahooBestComparable | None = None


def match_status_for_score(score: int) -> str:
    """Map a matching score to accepted / near-miss using config thresholds."""
    if score >= COMPARABLE_SCORE_THRESHOLD:
        return MATCH_STATUS_ACCEPTED
    if score >= NEAR_MISS_SCORE_THRESHOLD:
        return MATCH_STATUS_NEAR_MISS
    return MATCH_STATUS_HARD_REJECTED


def candidate_from_best_comparable(
    best: YahooBestComparable | None,
    *,
    marketplace: str,
    match_status: str | None = None,
) -> ComparableCandidate | None:
    """Convert an existing best-comparable result into a neutral candidate."""
    if best is None:
        return None
    status = match_status or match_status_for_score(int(best.matching_score))
    return ComparableCandidate(
        marketplace=marketplace,
        title=best.title,
        price_jpy=int(best.price_jpy),
        listing_url=best.url,
        condition=best.condition,
        matching_score=int(best.matching_score),
        matched_attributes=best.matched_attributes,
        match_status=status,
        identity_material=best.identity_material,
        identity_category=best.identity_category,
        source=best,
    )


def select_best_comparable_candidate(
    candidates: Sequence[ComparableCandidate | None] | None,
) -> ComparableCandidate | None:
    """Select the best comparable from zero or more marketplace candidates.

    Ordering (unchanged from prior Yahoo-vs-Mercari selector):
    1. Higher matching score
    2. Material identity present
    3. Category identity present
    On equal rank keys, earlier candidates win (stable first-max), matching
    the previous Yahoo-before-Mercari tie behavior when Yahoo is listed first.
    Hard-rejected candidates are never selectable.
    """
    pool = [
        item
        for item in (candidates or ())
        if item is not None and item.match_status != MATCH_STATUS_HARD_REJECTED
    ]
    if not pool:
        return None
    return max(pool, key=_rank_key)


def _rank_key(item: ComparableCandidate) -> tuple[int, int, int]:
    material_ok = item.identity_material not in {"", "UNKNOWN", "Unknown"}
    category_ok = item.identity_category not in {"", "UNKNOWN", "Unknown"}
    return (
        int(item.matching_score),
        1 if material_ok else 0,
        1 if category_ok else 0,
    )
