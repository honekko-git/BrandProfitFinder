"""Multi-brand model-family dictionary validation (false positives + extraction)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marketplace.browser_acquisition.bag_model_family import (
    FAMILY_ALMA,
    FAMILY_BIRKIN,
    FAMILY_CLEO,
    FAMILY_DIONYSUS,
    FAMILY_GALLERIA,
    FAMILY_JACKIE,
    FAMILY_KEEPALL,
    FAMILY_KELLY,
    FAMILY_MARMONT,
    FAMILY_NEVERFULL,
    FAMILY_PICOTIN,
    FAMILY_RE_EDITION,
    FAMILY_SPEEDY,
    build_bag_model_queries,
    extract_handbag_model_identity,
)
from marketplace.browser_acquisition.comparable_matching import RejectionReason, evaluate_comparables
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample


def _listing(title: str, brand: str) -> AcquiredListing:
    return AcquiredListing(
        external_id="p1",
        title=title,
        brand=brand,
        category="Bag",
        condition="UNKNOWN",
        price=Decimal("2000"),
        currency="USD",
        url="https://www.rebag.com/products/x",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Rebag",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int = 100000) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Mercari",
        auction_status="sold",
        url="https://jp.mercari.com/item/m1",
        condition="Good",
    )


@pytest.mark.parametrize(
    ("title", "brand", "family"),
    [
        ("Louis Vuitton Speedy 25 Monogram", "Louis Vuitton", FAMILY_SPEEDY),
        ("ルイヴィトン スピーディ25 モノグラム", "Louis Vuitton", FAMILY_SPEEDY),
        ("Hermès Kelly 28 Epsom", "Hermes", FAMILY_KELLY),
        ("エルメス ケリー28", "Hermes", FAMILY_KELLY),
        ("Gucci Dionysus Small GG Supreme", "Gucci", FAMILY_DIONYSUS),
        ("グッチ ディオニュソス", "Gucci", FAMILY_DIONYSUS),
        ("Prada Re-Edition 2005 Nylon", "Prada", FAMILY_RE_EDITION),
        ("プラダ リエディション ナイロン", "Prada", FAMILY_RE_EDITION),
    ],
)
def test_extracts_preferred_families(title: str, brand: str, family: str) -> None:
    identity = extract_handbag_model_identity(title=title, brand=brand, category="Bag")
    assert identity.model_family == family
    assert identity.positive_family_evidence


@pytest.mark.parametrize(
    ("purchase_title", "brand", "purchase_family", "wrong_titles", "wrong_families"),
    [
        (
            "Louis Vuitton Speedy 25 Monogram",
            "Louis Vuitton",
            FAMILY_SPEEDY,
            [
                "ルイヴィトン キーポル50 モノグラム",
                "ルイヴィトン アルマBB エピ",
                "ルイヴィトン ネヴァーフル MM モノグラム",
            ],
            [FAMILY_KEEPALL, FAMILY_ALMA, FAMILY_NEVERFULL],
        ),
        (
            "Hermès Kelly 28 Gold",
            "Hermes",
            FAMILY_KELLY,
            [
                "エルメス バーキン30 トゴ",
                "エルメス ピコタンロック 18",
            ],
            [FAMILY_BIRKIN, FAMILY_PICOTIN],
        ),
        (
            "Gucci Dionysus Shoulder Bag",
            "Gucci",
            FAMILY_DIONYSUS,
            [
                "グッチ GGマーモント ショルダー",
                "グッチ ジャッキー1961",
            ],
            [FAMILY_MARMONT, FAMILY_JACKIE],
        ),
        (
            "Prada Re-Edition Nylon Bag",
            "Prada",
            FAMILY_RE_EDITION,
            [
                "プラダ ガレリア サフィアーノ",
                "プラダ クレオ ブラッシュ",
            ],
            [FAMILY_GALLERIA, FAMILY_CLEO],
        ),
    ],
)
def test_false_positive_families_rejected(
    purchase_title: str,
    brand: str,
    purchase_family: str,
    wrong_titles: list[str],
    wrong_families: list[str],
) -> None:
    purchase = _listing(purchase_title, brand)
    assert extract_handbag_model_identity(title=purchase_title, brand=brand, category="Bag").model_family == purchase_family
    for title, expected_family in zip(wrong_titles, wrong_families, strict=True):
        sample_id = extract_handbag_model_identity(title=title, brand=brand, category="Bag")
        assert sample_id.model_family == expected_family, title
        result = evaluate_comparables(purchase, [_sample(title)], purchase_price_jpy=Decimal("400000"))
        assert not result.accepted_diagnostics, title
        reasons = set(result.rejected_diagnostics[0].rejection_reasons)
        assert reasons & {
            RejectionReason.DISTINCT_PRODUCT_FAMILY.value,
            RejectionReason.MODEL_FAMILY_CONFLICT.value,
        }, (title, reasons)


def test_queries_are_model_first_not_brand_bag_only() -> None:
    for title, brand, token in (
        ("Louis Vuitton Speedy 25", "Louis Vuitton", "スピーディ"),
        ("Hermès Kelly 28", "Hermes", "ケリー"),
        ("Gucci Dionysus", "Gucci", "ディオニュソス"),
        ("Prada Re-Edition Nylon", "Prada", "リエディション"),
    ):
        identity = extract_handbag_model_identity(title=title, brand=brand, category="Bag")
        queries = build_bag_model_queries(identity, brand=brand)
        assert queries
        assert any(token in q for q in queries)
        assert not queries[0].endswith("バッグ") or token in queries[0]
