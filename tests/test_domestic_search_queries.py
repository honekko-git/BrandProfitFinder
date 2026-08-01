"""Focused tests for marketplace-neutral domestic query generation."""

from __future__ import annotations

from marketplace.browser_acquisition.comparable_quality import classify_comparable_quality
from marketplace.browser_acquisition.domestic_search_queries import (
    MAX_SEARCH_QUERIES,
    STATUS_NO_SAFE_QUERY,
    TIER_CATEGORY_FALLBACK,
    TIER_REFERENCE_EXACT,
    TIER_REFERENCE_EXACT_EN,
    build_domestic_search_queries,
)
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries


def test_exact_reference_generates_jp_and_en_queries() -> None:
    result = build_domestic_search_queries(
        title="Prada Acetate Oval Sunglasses SPR 26Z-F Black",
        brand="Prada",
        category="Sunglasses",
    )
    assert result.queries
    assert any(q.tier == TIER_REFERENCE_EXACT for q in result.queries)
    assert any(q.tier == TIER_REFERENCE_EXACT_EN for q in result.queries)
    strings = result.query_strings
    assert any("SPR26Z" in q or "SPR26ZF" in q for q in strings)
    assert any("プラダ" in q for q in strings)
    assert any("Prada" in q for q in strings)
    assert result.status != STATUS_NO_SAFE_QUERY


def test_collection_family_generates_model_first_queries() -> None:
    result = build_domestic_search_queries(
        title="Prada Saffiano Lux Medium Tote Black",
        brand="Prada",
        category="Bag",
    )
    joined = " | ".join(result.query_strings).lower()
    assert "saffiano" in joined or "サフィアーノ" in joined
    assert result.queries[0].tier not in {TIER_CATEGORY_FALLBACK}
    assert not result.query_strings[0] in {"プラダ バッグ", "Prada bag"}


def test_material_size_enriches_without_replacing_identity() -> None:
    result = build_domestic_search_queries(
        title="Prada Saffiano Lux Medium Tote Black",
        brand="Prada",
        category="Bag",
    )
    assert result.identity_snapshot.get("collection") or result.identity_snapshot.get("family")
    # Primary query must include model identity, not only brand+category
    primary = result.query_strings[0].lower()
    assert "バッグ" not in primary or "saffiano" in primary or "サフィアーノ" in primary or "lux" in primary


def test_generic_brand_category_not_primary_when_stronger_identity() -> None:
    result = build_domestic_search_queries(
        title="Prada Acetate Symbole Sunglasses SPR 17W Havana",
        brand="Prada",
        category="Bag",  # mislabeled on purpose
    )
    assert result.query_strings
    assert result.query_strings[0] not in {"プラダ バッグ", "Prada bag"}
    assert any("SPR17W" in q for q in result.query_strings)


def test_category_only_fallback_labeled_and_cannot_publish_alone() -> None:
    result = build_domestic_search_queries(
        title="Prada Tessuto Nylon Tote Black",
        brand="Prada",
        category="Bag",
    )
    # May use fallback or soft tokens; if fallback, must be labeled.
    if any(q.tier == TIER_CATEGORY_FALLBACK for q in result.queries):
        assert "CATEGORY_FALLBACK" in result.status or "FALLBACK" in result.reason
    # Quality gate still refuses category-only comps
    report = classify_comparable_quality(
        purchase_price_jpy=100000,
        accepted_samples=[],
        accepted_diagnostics=[],
        comparable_warning="",
        filter_counts={"sold_kept": 0},
    )
    assert report.publish_price is False


def test_valid_identity_never_unexplained_empty() -> None:
    result = build_domestic_search_queries(
        title="Prada Galleria Small Double Zip Tote",
        brand="Prada",
        category="Bag",
    )
    assert result.query_strings
    assert result.status != STATUS_NO_SAFE_QUERY or result.reason


def test_no_safe_query_reason_persisted_when_empty_identity() -> None:
    result = build_domestic_search_queries(title="", brand="", category="")
    assert result.status == STATUS_NO_SAFE_QUERY
    assert result.reason
    payload = result.to_dict()
    assert payload["status"] == STATUS_NO_SAFE_QUERY
    assert payload["reason"]


def test_query_deduplication_and_cap() -> None:
    result = build_domestic_search_queries(
        title="Prada Saffiano Lux Medium Tote Black",
        brand="Prada",
        category="Bag",
        max_queries=MAX_SEARCH_QUERIES,
    )
    assert len(result.query_strings) <= MAX_SEARCH_QUERIES
    assert len(result.query_strings) == len(set(q.casefold() for q in result.query_strings))


def test_yahoo_and_mercari_receive_same_generated_queries() -> None:
    title = "Prada Acetate Sunglasses SPR 14Y Black"
    brand = "Prada"
    category = "Sunglasses"
    yahoo = build_yahoo_search_queries(title=title, brand=brand, category=category)
    mercari = build_mercari_search_queries(title=title, brand=brand, category=category)
    assert yahoo
    assert yahoo == mercari
    assert any("SPR14Y" in q for q in yahoo)


def test_trace_dict_preserves_tiers() -> None:
    result = build_domestic_search_queries(
        title="Prada SPR26Z Sunglasses",
        brand="Prada",
        category="Sunglasses",
    )
    payload = result.to_dict()
    assert payload["queries"]
    assert "tier" in payload["queries"][0]
    assert "signals" in payload["queries"][0]
