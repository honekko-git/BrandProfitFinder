"""Tests for candidate deduplication."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from marketplace.acquisition_workspace.deduplication import (
    deduplicate_candidates,
    merge_duplicate,
    unmerge_duplicate,
)
from tests.acquisition_test_helpers import make_candidate


def test_exact_url_duplicate() -> None:
    first = make_candidate(purchase_url="https://example.com/item?utm_source=x")
    second = replace(
        make_candidate(purchase_url="https://example.com/item?gclid=abc"),
        candidate_id="ac-second",
    )
    result = deduplicate_candidates([first, second])
    assert result[1].duplicate_of == first.candidate_id
    assert result[1].duplicate_reason == "duplicate URL"


def test_external_id_duplicate() -> None:
    first = make_candidate(external_id="fp-001", source_name="Fashionphile", purchase_url="https://example.com/a")
    second = replace(
        make_candidate(external_id="fp-001", source_name="Fashionphile", purchase_url="https://example.com/b"),
        candidate_id="ac-second",
    )
    result = deduplicate_candidates([first, second])
    assert result[1].duplicate_of == first.candidate_id


def test_title_price_duplicate() -> None:
    first = make_candidate(title="Chanel Wallet", purchase_price=Decimal("695"), purchase_url="https://example.com/a")
    second = replace(
        make_candidate(title="Chanel Wallet", purchase_price=Decimal("695"), purchase_url="https://example.com/b"),
        candidate_id="ac-second",
    )
    result = deduplicate_candidates([first, second])
    assert result[1].duplicate_of == first.candidate_id


def test_high_similarity_duplicate() -> None:
    first = make_candidate(
        title="Chanel Classic Wallet Black Caviar Leather",
        purchase_url="https://example.com/a",
    )
    second = replace(
        make_candidate(
            title="Chanel Classic Wallet Black Caviar Leathers",
            purchase_url="https://example.com/b",
        ),
        candidate_id="ac-second",
    )
    result = deduplicate_candidates([first, second])
    assert result[1].duplicate_of == first.candidate_id
    assert "similarity" in result[1].duplicate_reason


def test_merge_and_unmerge() -> None:
    primary = make_candidate()
    duplicate = replace(make_candidate(purchase_url="https://example.com/other"), candidate_id="ac-dup")
    _, merged = merge_duplicate(primary, duplicate)
    assert merged.duplicate_of == primary.candidate_id
    restored = unmerge_duplicate(merged)
    assert restored.duplicate_of == ""
    assert restored.eligible_for_profit_check
