"""Focused tests for marketplace-neutral comparable selection."""

from __future__ import annotations

from marketplace.browser_acquisition.comparable_candidate import (
    MATCH_STATUS_ACCEPTED,
    MATCH_STATUS_HARD_REJECTED,
    MATCH_STATUS_NEAR_MISS,
    ComparableCandidate,
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.mercari_comparable import choose_best_marketplace_comparable
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable


def _candidate(
    *,
    marketplace: str,
    title: str,
    score: int,
    match_status: str = MATCH_STATUS_ACCEPTED,
    material: str = "",
    category: str = "",
    price_jpy: int = 100000,
) -> ComparableCandidate:
    source = YahooBestComparable(
        title=title,
        price_jpy=price_jpy,
        url=f"https://example.invalid/{marketplace}/{title}",
        matching_score=score,
        matched_attributes=f"score:{score}",
        identity_material=material,
        identity_category=category,
    )
    return ComparableCandidate(
        marketplace=marketplace,
        title=title,
        price_jpy=price_jpy,
        listing_url=source.url,
        condition="",
        matching_score=score,
        matched_attributes=source.matched_attributes,
        match_status=match_status,
        identity_material=material,
        identity_category=category,
        source=source,
    )


def test_yahoo_wins_when_score_higher() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(marketplace="Yahoo Auctions", title="yahoo", score=90),
            _candidate(marketplace="Mercari", title="mercari", score=70),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Yahoo Auctions"
    assert selected.title == "yahoo"


def test_mercari_wins_when_score_higher() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(marketplace="Yahoo Auctions", title="yahoo", score=70),
            _candidate(marketplace="Mercari", title="mercari", score=85, material="CAVIAR"),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Mercari"
    assert selected.title == "mercari"


def test_tie_break_preserves_earlier_candidate_when_rank_keys_equal() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(marketplace="Yahoo Auctions", title="yahoo", score=80, material="CAVIAR", category="WALLET"),
            _candidate(marketplace="Mercari", title="mercari", score=80, material="CAVIAR", category="WALLET"),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Yahoo Auctions"
    # Compatibility wrapper uses the same Yahoo-first order.
    best, marketplace = choose_best_marketplace_comparable(
        YahooBestComparable(
            title="yahoo",
            price_jpy=100000,
            url="https://auctions.yahoo.co.jp/jp/auction/x1",
            matching_score=80,
            matched_attributes="score:80",
            identity_material="CAVIAR",
            identity_category="WALLET",
        ),
        YahooBestComparable(
            title="mercari",
            price_jpy=100000,
            url="https://jp.mercari.com/item/m1",
            matching_score=80,
            matched_attributes="score:80",
            identity_material="CAVIAR",
            identity_category="WALLET",
        ),
    )
    assert marketplace == "Yahoo Auctions"
    assert best is not None
    assert best.title == "yahoo"


def test_hard_rejected_candidate_cannot_win() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(
                marketplace="Hard Reject Market",
                title="rejected",
                score=99,
                match_status=MATCH_STATUS_HARD_REJECTED,
                material="CAVIAR",
            ),
            _candidate(marketplace="Mercari", title="ok", score=70),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Mercari"
    assert selected.title == "ok"


def test_near_miss_candidate_can_be_selected() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(
                marketplace="Yahoo Auctions",
                title="near",
                score=50,
                match_status=MATCH_STATUS_NEAR_MISS,
            )
        ]
    )
    assert selected is not None
    assert selected.match_status == MATCH_STATUS_NEAR_MISS
    assert selected.matching_score == 50


def test_empty_candidate_collection_returns_none() -> None:
    assert select_best_comparable_candidate([]) is None
    assert select_best_comparable_candidate(None) is None
    assert select_best_comparable_candidate([None, None]) is None


def test_single_candidate_works_without_marketplace_branching() -> None:
    selected = select_best_comparable_candidate(
        [_candidate(marketplace="Rebag", title="solo", score=75, material="LEATHER")]
    )
    assert selected is not None
    assert selected.marketplace == "Rebag"
    assert selected.title == "solo"


def test_three_or_more_candidates_evaluated_without_source_branches() -> None:
    selected = select_best_comparable_candidate(
        [
            _candidate(marketplace="Yahoo Auctions", title="yahoo", score=72),
            _candidate(marketplace="Mercari", title="mercari", score=78),
            _candidate(
                marketplace="Rebag",
                title="rebag",
                score=88,
                material="CAVIAR",
                category="WALLET",
            ),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Rebag"
    assert selected.title == "rebag"


def test_candidate_from_best_comparable_preserves_fields() -> None:
    best = YahooBestComparable(
        title="シャネル",
        price_jpy=180000,
        url="https://jp.mercari.com/item/m1",
        matching_score=85,
        matched_attributes="material:CAVIAR",
        condition="Very Good",
        identity_material="CAVIAR",
        identity_category="WALLET",
    )
    candidate = candidate_from_best_comparable(best, marketplace="Mercari")
    assert candidate is not None
    assert candidate.marketplace == "Mercari"
    assert candidate.listing_url == best.url
    assert candidate.match_status == MATCH_STATUS_ACCEPTED
    assert candidate.source is best
