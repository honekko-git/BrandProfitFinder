"""Resolve arbitrage opportunities from discovery pipeline results."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.arbitrage.market_listings import (
    enrich_listing_metadata,
    resolve_purchase_listing,
    resolve_selling_listing,
)
from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.arbitrage.scorer import ArbitrageScorer
from profit_discovery.arbitrage.sources import (
    build_purchase_url,
    build_selling_url,
    normalize_purchase_source,
    normalize_selling_market,
)
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_intelligence.demand.models import SalesDemandProfile
from profit_intelligence.normalization import clamp_score, piecewise_linear_score
from marketplace.connectors.resolver import MarketConnectorResolver
from supplier.models import SupplierType

SOLD_COUNT_TURNOVER_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (5.0, 35.0),
    (10.0, 55.0),
    (20.0, 75.0),
    (50.0, 90.0),
    (100.0, 100.0),
)


class ArbitrageOpportunityResolver:
    """Build arbitrage opportunities from demand-integrated discovery results."""

    def __init__(
        self,
        *,
        config: UsedLuxuryModeConfig | None = None,
        scorer: ArbitrageScorer | None = None,
        market_connector_resolver: MarketConnectorResolver | None = None,
    ) -> None:
        self._config = config or UsedLuxuryModeConfig.default()
        self._scorer = scorer or ArbitrageScorer()
        self._market_connector_resolver = market_connector_resolver or MarketConnectorResolver()
        self._allowed_brands = {brand.lower() for brand in self._config.all_brand_names()}

    def resolve_many(
        self,
        opportunities: list[DemandIntegratedOpportunityResult]
        | tuple[DemandIntegratedOpportunityResult, ...],
    ) -> list[ArbitrageOpportunity]:
        """Resolve arbitrage opportunities for used luxury candidates."""
        resolved: list[ArbitrageOpportunity] = []
        for item in opportunities:
            opportunity = self.resolve_one(item)
            if opportunity is not None:
                resolved.append(opportunity)
        return resolved

    def resolve_one(
        self,
        item: DemandIntegratedOpportunityResult,
    ) -> ArbitrageOpportunity | None:
        """Resolve one arbitrage opportunity when the candidate qualifies."""
        candidate = item.candidate
        if not self._is_eligible(candidate):
            return None

        product = candidate.supplier_product
        profit_result = candidate.profit_result
        if profit_result is None:
            return None

        purchase_price = _resolve_decimal(
            profit_result.purchase_price_jpy,
            fallback=Decimal(str(product.purchase_price)),
        )
        selling_price = _resolve_decimal(
            profit_result.domestic_sale_price_jpy,
            fallback=_resolve_selling_price(candidate),
        )
        if selling_price is None or purchase_price is None:
            return None

        price_difference = selling_price - purchase_price
        estimated_profit = profit_result.profit_jpy
        profit_margin = profit_result.profit_margin
        demand_score = _resolve_demand_score(item.demand_profile)
        turnover_score = _score_turnover(item.demand_profile)
        purchase_source = normalize_purchase_source(product.supplier_name)
        selling_market = _resolve_selling_market(candidate, item.demand_profile)
        product_name = (
            item.demand_profile.query
            if item.demand_profile is not None
            else product.title
        )
        purchase_url = build_purchase_url(purchase_source, product.url)
        selling_url = build_selling_url(
            selling_market,
            keyword=candidate.market_evaluation.matched_keyword
            if candidate.market_evaluation is not None
            else product.title,
        )
        purchase_listing = resolve_purchase_listing(
            product,
            connector_resolver=self._market_connector_resolver,
        )
        selling_listing = resolve_selling_listing(
            selling_market=selling_market,
            keyword=candidate.market_evaluation.matched_keyword
            if candidate.market_evaluation is not None
            else product.title,
            selling_url=selling_url,
            connector_resolver=self._market_connector_resolver,
        )
        market_source, condition, listing_url = enrich_listing_metadata(
            purchase_listing=purchase_listing,
            selling_listing=selling_listing,
            fallback_market_source=purchase_source,
            fallback_condition=product.condition,
            fallback_listing_url=purchase_url or selling_url,
        )

        base = ArbitrageOpportunity(
            product=product_name,
            brand=product.brand,
            category=product.category,
            purchase_source=purchase_source,
            purchase_url=purchase_url,
            purchase_price=purchase_price,
            selling_market=selling_market,
            selling_url=selling_url,
            selling_price=selling_price,
            price_difference=price_difference,
            estimated_profit=estimated_profit,
            profit_margin=profit_margin,
            demand_score=demand_score,
            turnover_score=turnover_score,
            arbitrage_score=0.0,
            decision=candidate.buy_decision.decision.value if candidate.buy_decision else "N/A",
            external_id=product.external_id,
            market_source=market_source,
            condition=condition,
            listing_url=listing_url,
        )
        score = self._scorer.score(base)
        return ArbitrageOpportunity(
            product=base.product,
            brand=base.brand,
            category=base.category,
            purchase_source=base.purchase_source,
            purchase_url=base.purchase_url,
            purchase_price=base.purchase_price,
            selling_market=base.selling_market,
            selling_url=base.selling_url,
            selling_price=base.selling_price,
            price_difference=base.price_difference,
            estimated_profit=base.estimated_profit,
            profit_margin=base.profit_margin,
            demand_score=base.demand_score,
            turnover_score=base.turnover_score,
            arbitrage_score=score.total_score,
            decision=base.decision,
            external_id=base.external_id,
            market_source=base.market_source,
            condition=base.condition,
            listing_url=base.listing_url,
        )

    def _is_eligible(self, candidate: DiscoveryCandidateResult) -> bool:
        if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
            return False
        product = candidate.supplier_product
        if not _is_used_product(product.condition):
            return False
        return product.brand.strip().lower() in self._allowed_brands


def _is_used_product(condition: str) -> bool:
    normalized = condition.strip().upper()
    return normalized in {SupplierType.USED.value, "PREOWNED", "PRE-OWNED"}


def _resolve_decimal(
    primary: Decimal | None,
    *,
    fallback: Decimal | None = None,
) -> Decimal | None:
    if primary is not None:
        return primary
    return fallback


def _resolve_selling_price(candidate: DiscoveryCandidateResult) -> Decimal | None:
    market_evaluation = candidate.market_evaluation
    if market_evaluation is None or market_evaluation.domestic_market_price is None:
        return None
    return Decimal(str(int(market_evaluation.domestic_market_price.average_price_jpy)))


def _resolve_selling_market(
    candidate: DiscoveryCandidateResult,
    demand_profile: SalesDemandProfile | None,
) -> str:
    market_evaluation = candidate.market_evaluation
    if market_evaluation is not None:
        sources = market_evaluation.metadata.get("sources")
        if isinstance(sources, list) and sources:
            for raw in sources:
                normalized = normalize_selling_market(str(raw))
                if normalized in {"Mercari", "Yahoo Auction"}:
                    return normalized
        raw_source = market_evaluation.metadata.get("source")
        if isinstance(raw_source, str) and raw_source.strip():
            return normalize_selling_market(raw_source)

    if demand_profile is not None and "mercari" in demand_profile.query.lower():
        return "Mercari"
    return "Yahoo Auction"


def _resolve_demand_score(demand_profile: SalesDemandProfile | None) -> float:
    if demand_profile is None:
        return 0.0
    return clamp_score(demand_profile.demand_score)


def _score_turnover(demand_profile: SalesDemandProfile | None) -> float:
    if demand_profile is None:
        return 0.0
    sold_component = piecewise_linear_score(
        float(demand_profile.sold_count),
        SOLD_COUNT_TURNOVER_THRESHOLDS,
    )
    sell_through_component = clamp_score(demand_profile.sell_through_rate * 100.0)
    return clamp_score(sold_component * 0.55 + sell_through_component * 0.45)
