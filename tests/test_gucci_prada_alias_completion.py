"""Focused alias and false-positive tests for Gucci Dionysus / Prada Re-Edition."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marketplace.browser_acquisition.bag_model_family import (
    FAMILY_CLEO,
    FAMILY_DIONYSUS,
    FAMILY_GALLERIA,
    FAMILY_JACKIE,
    FAMILY_MARMONT,
    FAMILY_RE_EDITION,
    build_bag_model_queries,
    extract_handbag_model_identity,
)
from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.model_dictionaries import load_model_dictionaries
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample


def _listing(title: str, brand: str) -> AcquiredListing:
    return AcquiredListing(
        external_id="p1",
        title=title,
        brand=brand,
        category="Bag",
        condition="UNKNOWN",
        price=Decimal("1800"),
        currency="USD",
        url="https://www.rebag.com/products/x",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Vestiaire Collective",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int = 120000) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Mercari",
        auction_status="sold",
        url="https://jp.mercari.com/item/m1",
        condition="Good",
    )


@pytest.fixture(autouse=True)
def _clear_dict_cache() -> None:
    load_model_dictionaries.cache_clear()
    yield
    load_model_dictionaries.cache_clear()


@pytest.mark.parametrize(
    "title",
    [
        "グッチ ディオニュソス ショルダー",
        "グッチ ディオニソス バッグ",
        "Gucci Dionysus GG Supreme",
        "GUCCI ディオニソス チェーン",
        "GUCCI 401231 ディオニュソス",
        "GGスプリーム ディオニュソス ショルダー",
    ],
)
def test_dionysus_aliases_recognized(title: str) -> None:
    identity = extract_handbag_model_identity(title=title, brand="Gucci", category="Bag")
    assert identity.model_family == FAMILY_DIONYSUS


def test_gg_supreme_alone_insufficient() -> None:
    identity = extract_handbag_model_identity(
        title="グッチ GGスプリーム ショルダーバッグ",
        brand="Gucci",
        category="Bag",
    )
    assert identity.model_family != FAMILY_DIONYSUS
    assert not identity.positive_family_evidence or identity.model_family == ""


def test_tiger_head_alone_insufficient() -> None:
    identity = extract_handbag_model_identity(
        title="グッチ タイガーヘッド 金具 チャーム",
        brand="Gucci",
        category="Bag",
    )
    assert identity.model_family != FAMILY_DIONYSUS


@pytest.mark.parametrize(
    ("title", "family"),
    [
        ("グッチ マーモント ショルダー", FAMILY_MARMONT),
        ("グッチ ジャッキー1961", FAMILY_JACKIE),
        ("グッチ オフィディア ショルダー", "Ophidia"),
        ("Gucci Bamboo Bag Black", "Bamboo"),
    ],
)
def test_other_gucci_families_distinct(title: str, family: str) -> None:
    purchase = _listing("Gucci Dionysus Handbag", "Gucci")
    sample_id = extract_handbag_model_identity(title=title, brand="Gucci", category="Bag")
    assert sample_id.model_family == family
    result = evaluate_comparables(purchase, [_sample(title)], purchase_price_jpy=Decimal("300000"))
    assert not result.accepted_diagnostics
    reasons = set(result.rejected_diagnostics[0].rejection_reasons)
    assert reasons & {
        RejectionReason.DISTINCT_PRODUCT_FAMILY.value,
        RejectionReason.MODEL_FAMILY_CONFLICT.value,
    }


def test_generic_gucci_bag_insufficient() -> None:
    result = evaluate_comparables(
        _listing("Gucci Dionysus Handbag", "Gucci"),
        [_sample("グッチ ショルダーバッグ レザー 黒")],
        purchase_price_jpy=Decimal("300000"),
    )
    assert not result.accepted_diagnostics
    assert (
        RejectionReason.GENERIC_SAME_BRAND_INSUFFICIENT.value
        in result.rejected_diagnostics[0].rejection_reasons
    )


def test_dionysus_shoulder_same_family_can_clear_threshold() -> None:
    """BAG purchase vs SHOULDER_BAG sold same-family must remain defensible."""
    result = evaluate_comparables(
        _listing("Gucci Dionysus Handbag", "Gucci"),
        [
            _sample("グッチ ディオニュソス チェーン ショルダーバッグ 401231"),
            _sample("GUCCI Dionysus Super Mini Bag 476432 ショルダー"),
            _sample("グッチ ディオニソス ショルダー GGスプリーム"),
        ],
        purchase_price_jpy=Decimal("300000"),
    )
    assert len(result.accepted_diagnostics) >= 3
    assert all(item.model_family == FAMILY_DIONYSUS for item in result.accepted_diagnostics)
    assert all(item.matching_score >= COMPARABLE_SCORE_THRESHOLD for item in result.accepted_diagnostics)


@pytest.mark.parametrize(
    "title",
    [
        "プラダ リエディション ナイロン",
        "プラダ リ・エディション",
        "Prada Re-Edition 2005",
        "Prada Re Edition Nylon",
        "プラダ リエディション2000",
        "プラダ リエディション2005",
        "PRADA 1BH204 Re-Edition",
        "プラダ リナイロン リエディション",
    ],
)
def test_reedition_aliases_recognized(title: str) -> None:
    identity = extract_handbag_model_identity(title=title, brand="Prada", category="Bag")
    assert identity.model_family == FAMILY_RE_EDITION


@pytest.mark.parametrize(
    "title",
    [
        "プラダ ナイロンバッグ 黒",
        "プラダ 三角ロゴ ミニバッグ",
        "プラダ テスート ショルダー",
    ],
)
def test_prada_generic_insufficient(title: str) -> None:
    identity = extract_handbag_model_identity(title=title, brand="Prada", category="Bag")
    assert identity.model_family != FAMILY_RE_EDITION
    result = evaluate_comparables(
        _listing("Prada Re-Edition Nylon Bag", "Prada"),
        [_sample(title)],
        purchase_price_jpy=Decimal("250000"),
    )
    assert not result.accepted_diagnostics


@pytest.mark.parametrize(
    ("title", "family"),
    [
        ("プラダ ガレリア サフィアーノ", FAMILY_GALLERIA),
        ("プラダ クレオ ブラッシュ", FAMILY_CLEO),
    ],
)
def test_prada_other_families_rejected(title: str, family: str) -> None:
    purchase = _listing("Prada Re-Edition Nylon Bag", "Prada")
    assert extract_handbag_model_identity(title=title, brand="Prada", category="Bag").model_family == family
    result = evaluate_comparables(purchase, [_sample(title)], purchase_price_jpy=Decimal("250000"))
    assert not result.accepted_diagnostics
    reasons = set(result.rejected_diagnostics[0].rejection_reasons)
    assert reasons & {
        RejectionReason.DISTINCT_PRODUCT_FAMILY.value,
        RejectionReason.MODEL_FAMILY_CONFLICT.value,
    }


def test_queries_model_first_and_safe() -> None:
    gucci = extract_handbag_model_identity(title="Gucci Dionysus Handbag", brand="Gucci", category="Bag")
    gq = build_bag_model_queries(gucci, brand="Gucci")
    assert gq and "ディオニュソス" in gq[0]
    assert not any(q == "グッチ バッグ" for q in gq)

    prada = extract_handbag_model_identity(title="Prada Re-Edition Nylon", brand="Prada", category="Bag")
    pq = build_bag_model_queries(prada, brand="Prada")
    assert pq and "リエディション" in " ".join(pq)
    assert "ナイロン ミニバッグ" not in " ".join(pq)


def test_no_brand_specific_engine_branches() -> None:
    from pathlib import Path

    source = Path("marketplace/browser_acquisition/bag_model_family.py").read_text(encoding="utf-8")
    assert "if brand ==" not in source
    assert 'brand == "Gucci"' not in source
    assert 'brand == "Prada"' not in source


def test_dictionary_has_no_duplicate_strong_aliases_across_same_brand() -> None:
    bundle = load_model_dictionaries()
    by_brand: dict[str, dict[str, str]] = {}
    for family in bundle.families:
        for brand in family.brand_keys or ("*",):
            bucket = by_brand.setdefault(brand, {})
            for alias in family.aliases:
                key = alias.lower()
                if key in bucket and bucket[key] != family.id:
                    raise AssertionError(f"duplicate strong alias {alias!r}: {bucket[key]} vs {family.id}")
                bucket[key] = family.id


def test_thresholds_unchanged() -> None:
    assert COMPARABLE_SCORE_THRESHOLD == 70
