"""Integration tests for profit intelligence pipeline."""

from decimal import Decimal
from unittest.mock import patch

import main
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from profit_intelligence.service import ProfitIntelligenceService


def _phase3_calculator() -> ProfitCalculator:
    return ProfitCalculator(
        ProfitConfig(
            international_shipping_jpy=Decimal("2500"),
            customs_duty_rate=Decimal("0.08"),
            import_tax_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("800"),
            marketplace_fee_rate=Decimal("0.12"),
            other_costs_jpy=Decimal("500"),
        )
    )


def test_pipeline_produces_scores_without_changing_profit() -> None:
    products = main.build_phase3_products()
    listings_map = main.build_phase3_listings()
    marketplace = main.create_marketplace(
        "local",
        listings_by_product_key=listings_map,
        selection_strategy=main.PriceSelectionStrategy.HIGHEST,
    )
    calculator = _phase3_calculator()
    search_results = [marketplace.search(product) for product in products]
    raw_results = main.calculate_profit_from_search_results(search_results, calculator)
    before = [(float(r.profit_jpy), float(r.profit_margin)) for r in raw_results]

    service = ProfitIntelligenceService()
    scored = service.score_results(raw_results, search_results)
    after = [(float(r.profit_jpy), float(r.profit_margin)) for r in scored]
    assert before == after
    assert all(item.profit_intelligence is not None for item in scored)


def test_legacy_ranking_when_scoring_disabled() -> None:
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = main.run(profit_intelligence=False)
    assert output_path.exists()


def test_scoring_enabled_run_succeeds() -> None:
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = main.run(profit_intelligence=True)
    assert output_path.exists()
