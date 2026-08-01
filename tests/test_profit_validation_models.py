"""Tests for profit validation models and scoring."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.discovery_validation.models import ValidationConfig, ValidationOpportunity
from profit_discovery.discovery_validation.validator import ProfitValidationValidator
from profit_discovery.models import BuyDecision


def _sample_opportunity() -> ValidationOpportunity:
    return ValidationOpportunity(
        product="Chanel Wallet",
        brand="Chanel",
        category="Wallet",
        purchase_source="Fashionphile",
        purchase_price=Decimal("50000"),
        purchase_url="https://example.invalid/purchase",
        domestic_market="Yahoo Auction",
        domestic_price=Decimal("150000"),
        domestic_url="https://example.invalid/selling",
        estimated_profit=Decimal("12000"),
        profit_margin=Decimal("24"),
        demand_score=70.0,
        turnover_score=55.0,
        validation_score=0.0,
        decision="N/A",
        external_id="validation-001",
    )
    return base


def test_validation_config_filters_tier_s_brands_and_categories() -> None:
    config = ValidationConfig()

    assert config.is_allowed_brand("Chanel")
    assert config.is_allowed_brand("louis vuitton")
    assert not config.is_allowed_brand("Gucci")
    assert config.is_allowed_category("Wallet")
    assert config.is_allowed_category("wallets")
    assert config.is_allowed_category("Mini Bag")
    assert not config.is_allowed_category("Shoes")


def test_profit_validation_validator_scores_and_decides_buy() -> None:
    validator = ProfitValidationValidator()
    opportunity = _sample_opportunity()
    score = validator.score(opportunity)

    assert score.total_score > 0
    assert score.profit_score > 0
    assert score.margin_score > 0
    assert validator.decide(opportunity) == BuyDecision.BUY.value

    validated = validator.validate_one(opportunity)
    assert validated.validation_score == score.total_score
    assert validated.decision == BuyDecision.BUY.value


def test_profit_validation_validator_passes_when_thresholds_not_met() -> None:
    validator = ProfitValidationValidator()
    opportunity = ValidationOpportunity(
        product="Chanel Wallet",
        brand="Chanel",
        category="Wallet",
        purchase_source="Fashionphile",
        purchase_price=Decimal("50000"),
        purchase_url="https://example.invalid/purchase",
        domestic_market="Yahoo Auction",
        domestic_price=Decimal("80000"),
        domestic_url="https://example.invalid/selling",
        estimated_profit=Decimal("5000"),
        profit_margin=Decimal("10"),
        demand_score=40.0,
        turnover_score=30.0,
        validation_score=0.0,
        decision="N/A",
        external_id="validation-002",
    )

    assert validator.decide(opportunity) == BuyDecision.PASS.value
