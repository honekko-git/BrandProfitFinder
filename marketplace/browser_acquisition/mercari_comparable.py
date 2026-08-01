"""Mercari comparable helpers and Yahoo/Mercari compatibility wrappers."""

from __future__ import annotations

from marketplace.browser_acquisition.comparable_candidate import (
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.comparable_matching import ComparableEstimateResult
from marketplace.browser_acquisition.models import AcquiredListing, YahooSoldSample
from marketplace.browser_acquisition.yahoo_comparable import (
    YahooBestComparable,
    select_best_yahoo_comparable,
)

MERCARI_MARKETPLACE = "Mercari"
YAHOO_MARKETPLACE = "Yahoo Auctions"


def select_best_mercari_comparable(
    purchase: AcquiredListing,
    result: ComparableEstimateResult,
    *,
    min_score: int | None = None,
    candidate_samples: tuple[YahooSoldSample, ...] | list[YahooSoldSample] | None = None,
) -> YahooBestComparable | None:
    """Choose the best Mercari comparable using existing matching scores."""
    return select_best_yahoo_comparable(
        purchase,
        result,
        min_score=min_score,
        candidate_samples=candidate_samples,
    )


def choose_best_marketplace_comparable(
    yahoo_best: YahooBestComparable | None,
    mercari_best: YahooBestComparable | None,
) -> tuple[YahooBestComparable | None, str]:
    """Compatibility wrapper: Yahoo + Mercari via marketplace-neutral selector.

    Candidate order is Yahoo then Mercari so equal-rank ties keep prior behavior
    (Yahoo wins when rank keys are equal).
    """
    selected = select_best_comparable_candidate(
        [
            candidate_from_best_comparable(yahoo_best, marketplace=YAHOO_MARKETPLACE),
            candidate_from_best_comparable(mercari_best, marketplace=MERCARI_MARKETPLACE),
        ]
    )
    if selected is None:
        return None, ""
    return selected.source, selected.marketplace
