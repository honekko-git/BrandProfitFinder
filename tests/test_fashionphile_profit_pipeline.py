"""Integration tests for Fashionphile supplier profit pipeline boundary."""

from __future__ import annotations

from decimal import Decimal

from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate


def _candidate_to_product(candidate: dict[str, object]) -> Product:
    return Product(
        name=str(candidate["name"]),
        brand=str(candidate["brand"]),
        price=float(candidate["purchase_price"]),
        currency=str(candidate["currency"]),
        store_name=str(candidate["source"]),
        url=str(candidate.get("url") or ""),
        model=str(candidate.get("model_number") or ""),
        exchange_rate=150.0,
    )


def test_fashionphile_product_flows_through_profit_pipeline() -> None:
    client = FashionphileClient()
    supplier_products = client.search_products("Gucci", max_results=1)
    assert supplier_products

    candidate = to_product_candidate(supplier_products[0])
    product = _candidate_to_product(candidate)
    calculator = ProfitCalculator()

    price_result = calculator.calculate(product, Decimal("300000"), domestic_market="manual")

    assert price_result.calculation_status == "success"
    assert price_result.profit_jpy > 0
    assert price_result.product is product


def test_fashionphile_product_flows_through_discovery_and_buy_decision() -> None:
    client = FashionphileClient()
    supplier_product = client.search_products("Louis Vuitton", max_results=1)[0]
    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate)
    calculator = ProfitCalculator()

    price_result = calculator.calculate(product, Decimal("250000"), domestic_market="manual")
    price_result.metadata.update(
        {
            "brand": supplier_product.brand.lower(),
            "identity_confidence_score": 0.85,
            "listing_count": 2,
        }
    )

    discovery = DiscoveryEngine().score(price_result)
    decision = BuyDecisionEngine().decide(price_result, discovery)

    assert discovery.overall_score >= 0
    assert decision.expected_profit_jpy == price_result.profit_jpy
    assert decision.decision.value in {"BUY", "HOLD", "PASS"}
