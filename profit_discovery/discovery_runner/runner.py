"""Batch orchestration for supplier discovery evaluation."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import CALCULATION_SUCCESS
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_runner.models import (
    BatchDiscoveryResult,
    DiscoveryCandidateResult,
    DiscoveryCandidateStatus,
)
from profit_discovery.market_connector.connector import SupplierMarketConnector
from profit_discovery.models import BuyDecision
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.base import SupplierClient
from supplier.models import SupplierProduct, to_product_candidate


class DiscoveryRunner:
    """Evaluate multiple supplier products through the existing discovery pipeline."""

    def __init__(
        self,
        *,
        supplier_client: SupplierClient,
        market_connector: SupplierMarketConnector,
        profit_calculator: ProfitCalculator | None = None,
        discovery_engine: DiscoveryEngine | None = None,
        buy_decision_engine: BuyDecisionEngine | None = None,
        exchange_rate: float = 150.0,
    ) -> None:
        self._supplier_client = supplier_client
        self._market_connector = market_connector
        self._profit_calculator = profit_calculator or ProfitCalculator()
        self._discovery_engine = discovery_engine or DiscoveryEngine()
        self._buy_decision_engine = buy_decision_engine or BuyDecisionEngine()
        self._exchange_rate = exchange_rate

    @property
    def supplier_client(self) -> SupplierClient:
        return self._supplier_client

    @property
    def market_connector(self) -> SupplierMarketConnector:
        return self._market_connector

    def evaluate_products(self, products: list[SupplierProduct]) -> BatchDiscoveryResult:
        """Evaluate a batch of supplier products without stopping on individual failures."""
        results: list[DiscoveryCandidateResult] = []
        for product in products:
            results.append(self._evaluate_one(product))

        buy_candidates = sum(
            1
            for result in results
            if result.status is DiscoveryCandidateStatus.SUCCESS
            and result.buy_decision is not None
            and result.buy_decision.decision is BuyDecision.BUY
        )

        return BatchDiscoveryResult(
            total_products=len(products),
            evaluated_products=len(results),
            buy_candidates=buy_candidates,
            results=tuple(results),
            metadata={"supplier_name": self._supplier_client.supplier_name},
        )

    def _evaluate_one(self, product: SupplierProduct) -> DiscoveryCandidateResult:
        try:
            market_evaluation = self._market_connector.evaluate_product(product)
            if market_evaluation.domestic_market_price is None:
                return DiscoveryCandidateResult(
                    supplier_product=product,
                    status=DiscoveryCandidateStatus.NO_MARKET_DATA,
                    market_evaluation=market_evaluation,
                    metadata={"reason": "no_domestic_market_price"},
                )

            candidate = to_product_candidate(product)
            model_product = _candidate_to_product(candidate, exchange_rate=self._exchange_rate)
            domestic_sale = Decimal(
                str(int(market_evaluation.domestic_market_price.average_price_jpy))
            )
            profit_result = self._profit_calculator.calculate(
                model_product,
                domestic_sale,
                domestic_market="yahoo_auction",
            )

            if profit_result.calculation_status != CALCULATION_SUCCESS:
                return DiscoveryCandidateResult(
                    supplier_product=product,
                    status=DiscoveryCandidateStatus.ERROR,
                    market_evaluation=market_evaluation,
                    profit_result=profit_result,
                    metadata={"reason": "profit_calculation_failed"},
                )

            profit_result.metadata.update(
                {
                    "brand": product.brand.lower(),
                    "identity_confidence_score": 0.85,
                    "listing_count": market_evaluation.metadata.get("sample_count", 1),
                    "market_signal_confidence_score": market_evaluation.confidence_score,
                }
            )

            discovery_score = self._discovery_engine.score(profit_result)
            buy_decision = self._buy_decision_engine.decide(profit_result, discovery_score)

            return DiscoveryCandidateResult(
                supplier_product=product,
                status=DiscoveryCandidateStatus.SUCCESS,
                market_evaluation=market_evaluation,
                profit_result=profit_result,
                discovery_score=discovery_score,
                buy_decision=buy_decision,
            )
        except Exception as exc:
            return DiscoveryCandidateResult(
                supplier_product=product,
                status=DiscoveryCandidateStatus.ERROR,
                metadata={"reason": "unexpected_error", "error": str(exc)},
            )


def _candidate_to_product(candidate: dict[str, object], *, exchange_rate: float) -> object:
    from models.product import Product

    return Product(
        name=str(candidate["name"]),
        brand=str(candidate["brand"]),
        price=float(candidate["purchase_price"]),
        currency=str(candidate["currency"]),
        store_name=str(candidate["source"]),
        url=str(candidate.get("url") or ""),
        model=str(candidate.get("model_number") or ""),
        exchange_rate=exchange_rate,
    )
