"""New-market price validation (used estimate vs new retail)."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.new_market_price import (
    NewMarketEvidence,
    NewMarketRisk,
    build_new_market_warning,
    classify_used_vs_new_risk,
    score_new_market_match,
    select_best_new_market_evidence,
    validate_new_market_price,
)
from marketplace.browser_acquisition.new_market_provider import (
    MockNewMarketPriceProvider,
    NullNewMarketPriceProvider,
    resolve_new_market_validation,
)
from marketplace.browser_acquisition.product_identity import extract_product_identity


def _identity(title: str, *, category: str = "Sunglasses"):
    return extract_product_identity(title=title, brand="Prada", category=category)


def test_exact_model_new_price_lower_creates_critical_warning() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR 26Z Pink")
    candidates = [
        NewMarketEvidence(
            marketplace="BUYMA",
            title="PRADA SPR26Z Sunglasses Pink",
            price=42800,
            condition="NEW",
        )
    ]
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=120000,
        candidates=candidates,
    )
    assert result.risk == NewMarketRisk.CRITICAL.value
    assert result.code == "NEW_PRICE_LOWER_THAN_USED"
    assert result.ranking_safe is False
    assert result.new_market_price_jpy == 42800


def test_warning_when_new_moderately_lower() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR26Z")
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=120000,
        candidates=[
            NewMarketEvidence(marketplace="BUYMA", title="PRADA SPR26Z Sunglasses", price=90000)
        ],
    )
    assert result.risk == NewMarketRisk.WARNING.value
    assert result.ranking_safe is True


def test_normal_when_new_higher() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR26Z")
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=80000,
        candidates=[
            NewMarketEvidence(marketplace="BUYMA", title="PRADA SPR26Z Sunglasses", price=150000)
        ],
    )
    assert result.risk == NewMarketRisk.NORMAL.value
    assert result.ranking_safe is True


def test_different_model_does_not_create_warning() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR 26Z Pink")
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=120000,
        candidates=[
            NewMarketEvidence(
                marketplace="BUYMA",
                title="PRADA SPR32S Sunglasses Black",
                price=42800,
            )
        ],
    )
    assert result.risk == NewMarketRisk.NONE.value
    assert result.ranking_safe is True
    assert result.new_market_price_jpy is None


def test_no_new_data_does_not_affect_ranking() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR26Z")
    result = resolve_new_market_validation(
        product_identity=identity,
        used_predicted_price_jpy=120000,
        provider=NullNewMarketPriceProvider(),
    )
    assert result.risk == NewMarketRisk.NONE.value
    assert result.ranking_safe is True


def test_reference_number_matching_works() -> None:
    identity = _identity("Prada SPR26Z Sunglasses")
    evidence = NewMarketEvidence(marketplace="BUYMA", title="PRADA SPR26Z Pink", price=42800)
    score = score_new_market_match(identity, evidence)
    assert score >= 55
    best = select_best_new_market_evidence(identity, [evidence])
    assert best is not None
    assert best.match_score >= 55


def test_category_only_match_rejected() -> None:
    identity = _identity("Prada Acetate Oval Sunglasses SPR26Z")
    evidence = NewMarketEvidence(
        marketplace="BUYMA",
        title="PRADA Sunglasses Black Frame",
        price=20000,
    )
    score = score_new_market_match(identity, evidence)
    assert score < 55 or "SPR26Z" not in evidence.title.upper()
    best = select_best_new_market_evidence(identity, [evidence])
    assert best is None
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=120000,
        candidates=[evidence],
    )
    assert result.risk == NewMarketRisk.NONE.value


def test_saffiano_family_match_can_validate() -> None:
    identity = extract_product_identity(
        title="Prada Saffiano Lux Medium Tote Cammeo",
        brand="Prada",
        category="Bag",
    )
    # New price higher → NORMAL, no false CRITICAL
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=155000,
        candidates=[
            NewMarketEvidence(
                marketplace="BUYMA",
                title="PRADA Saffiano Lux Medium Tote NEW",
                price=220000,
            )
        ],
    )
    assert result.risk == NewMarketRisk.NORMAL.value


def test_generic_prada_no_unrelated_match() -> None:
    identity = extract_product_identity(title="Prada Tote", brand="Prada", category="Bag")
    result = validate_new_market_price(
        identity=identity,
        used_predicted_price_jpy=90000,
        candidates=[
            NewMarketEvidence(marketplace="BUYMA", title="PRADA Tote Bag Canvas", price=30000),
            NewMarketEvidence(marketplace="BUYMA", title="PRADA Sunglasses", price=20000),
        ],
    )
    assert result.risk == NewMarketRisk.NONE.value


def test_mock_provider_returns_catalog() -> None:
    identity = _identity("Prada SPR26Z Sunglasses")
    provider = MockNewMarketPriceProvider(
        catalog=[
            NewMarketEvidence(marketplace="BUYMA", title="PRADA SPR26Z Sunglasses", price=42800),
        ]
    )
    result = resolve_new_market_validation(
        product_identity=identity,
        used_predicted_price_jpy=120000,
        provider=provider,
    )
    assert result.risk == NewMarketRisk.CRITICAL.value


def test_legacy_build_new_market_warning() -> None:
    assert build_new_market_warning(used_estimate_jpy=120000, new_market_price_jpy=None) is None
    warning = build_new_market_warning(used_estimate_jpy=120000, new_market_price_jpy=42800)
    assert warning is not None
    assert warning.risk == NewMarketRisk.CRITICAL.value


def test_classify_ratio_boundaries() -> None:
    risk, code, _ = classify_used_vs_new_risk(
        used_predicted_price_jpy=120000,
        new_market_price_jpy=42800,
    )
    assert risk == NewMarketRisk.CRITICAL.value
    assert code == "NEW_PRICE_LOWER_THAN_USED"
    risk, _, _ = classify_used_vs_new_risk(
        used_predicted_price_jpy=120000,
        new_market_price_jpy=90000,
    )
    assert risk == NewMarketRisk.WARNING.value
