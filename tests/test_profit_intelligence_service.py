"""Tests for profit intelligence service."""

import copy
from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_intelligence.constants import SCORING_VERSION
from profit_intelligence.models import ProfitIntelligenceInput
from profit_intelligence.service import ProfitIntelligenceService


def test_direct_input_scoring() -> None:
    service = ProfitIntelligenceService()
    result = service.score_input(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("8000"),
            profit_margin_percent=Decimal("25"),
            sales_last_30_days=15,
            shipping_cost_known=True,
            marketplace_fee_known=True,
            duties_tax_known=True,
            currency="JPY",
        )
    )
    assert result.scoring_version == SCORING_VERSION
    assert result.confidence_score >= 0


def test_service_does_not_mutate_price_result() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    original = ProfitCalculator().calculate(product, Decimal("50000"))
    snapshot = copy.deepcopy(original)
    service = ProfitIntelligenceService()
    service.score_price_result(original)
    assert original.profit_jpy == snapshot.profit_jpy
    assert original.profit_margin == snapshot.profit_margin


def test_stockx_metadata_mapping() -> None:
    product = Product(name="Sneaker", brand="Nike", price=100.0, currency="USD", exchange_rate=150.0)
    result = ProfitCalculator().calculate(product, Decimal("50000"))
    result.metadata = {
        "source_currency": "JPY",
        "sales_last_30_days": 40,
        "sales_last_72_hours": 5,
        "asks_count": 8,
        "bids_count": 12,
        "volatility_rate": Decimal("0.12"),
        "source_style_code": "ABC123",
        "source_product_id": "prod-1",
        "fees_known": True,
        "shipping_known": True,
        "duties_known": True,
    }
    service = ProfitIntelligenceService()
    intelligence = service.score_price_result(result)
    assert intelligence.velocity_score is not None
    assert intelligence.scoring_version == SCORING_VERSION
