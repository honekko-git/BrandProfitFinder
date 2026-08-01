"""Tests for ranking table price display helpers."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from marketplace.acquisition_workspace.price_display import (
    analysis_badge,
    build_analysis_badges,
    build_price_cells,
    build_title_cells,
    format_yen,
    resolve_purchase_text,
    split_brand_title,
)


def test_format_yen_formats_positive_amounts() -> None:
    assert format_yen(Decimal("104250")) == "¥104,250"
    assert format_yen(0) == "-"
    assert format_yen(None) == "-"


def test_resolve_purchase_text_falls_back_to_record_cost() -> None:
    with_jpy = SimpleNamespace(purchase_price_jpy=Decimal("86000"), purchase_price=Decimal("0"), currency="USD")
    assert resolve_purchase_text(with_jpy) == "¥86,000"

    jpy_record = SimpleNamespace(purchase_price_jpy=Decimal("0"), purchase_price=Decimal("128000"), currency="JPY")
    assert resolve_purchase_text(jpy_record) == "¥128,000"

    usd_record = SimpleNamespace(purchase_price_jpy=None, purchase_price=Decimal("695"), currency="USD")
    assert resolve_purchase_text(usd_record) == "695 USD"


def test_build_price_cells_uses_existing_values_only() -> None:
    row = SimpleNamespace(
        candidate_id="c1",
        purchase_price_jpy=Decimal("86000"),
        purchase_price=Decimal("695"),
        currency="USD",
    )
    cells = build_price_cells(
        [row],
        selling_estimate_by_id={"c1": Decimal("128000")},
    )
    assert cells["c1"]["purchase"] == "¥86,000"
    assert cells["c1"]["selling"] == "¥128,000"
    assert cells["c1"]["selling_label"] == "販売予想"

    missing = build_price_cells([row], selling_estimate_by_id={})
    assert missing["c1"]["selling"] == "-"


def test_split_brand_title_and_title_cells() -> None:
    brand, product = split_brand_title("CHANEL", "CHANEL マトラッセ キャビアスキン 長財布")
    assert brand == "CHANEL"
    assert product == "マトラッセ キャビアスキン 長財布"
    row = SimpleNamespace(candidate_id="c1", brand="CHANEL", title="CHANEL マトラッセ キャビアスキン 長財布")
    cells = build_title_cells([row])
    assert cells["c1"]["brand"] == "CHANEL"
    assert cells["c1"]["product"] == "マトラッセ キャビアスキン 長財布"


def test_analysis_badge_uses_existing_confidence() -> None:
    assert analysis_badge("高") == "◎"
    assert analysis_badge("HIGH") == "◎"
    assert analysis_badge("中") == "○"
    assert analysis_badge("LOW") == "△"
    assert analysis_badge("HIGH", has_warning=True) == "⚠"


def test_build_analysis_badges_for_template() -> None:
    row = SimpleNamespace(
        candidate_id="c1",
        data_truth_summary=SimpleNamespace(confidence_level="HIGH"),
    )
    rank = SimpleNamespace(confidence_level="高")
    badges = build_analysis_badges(
        [row],
        {"c1": rank},
        url_warning_fn=lambda _row: None,
    )
    assert badges["c1"] == "◎"
    warned = build_analysis_badges(
        [row],
        {},
        url_warning_fn=lambda _row: "invalid url",
    )
    assert warned["c1"] == "⚠"
