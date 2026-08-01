"""Ranking helpers for used luxury arbitrage opportunities."""

from __future__ import annotations

from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.arbitrage.resolver import ArbitrageOpportunityResolver
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult


def create_arbitrage_ranking(
    opportunities: list[DemandIntegratedOpportunityResult]
    | tuple[DemandIntegratedOpportunityResult, ...],
    *,
    config: UsedLuxuryModeConfig | None = None,
    resolver: ArbitrageOpportunityResolver | None = None,
) -> list[ArbitrageOpportunity]:
    """Create a ranked used luxury arbitrage list ordered by profit plus sellability."""
    active_config = config or UsedLuxuryModeConfig.default()
    active_resolver = resolver or ArbitrageOpportunityResolver(config=active_config)
    resolved = active_resolver.resolve_many(opportunities)
    ranked = sorted(resolved, key=_rank_key)
    return [
        ArbitrageOpportunity(
            product=item.product,
            brand=item.brand,
            category=item.category,
            purchase_source=item.purchase_source,
            purchase_url=item.purchase_url,
            purchase_price=item.purchase_price,
            selling_market=item.selling_market,
            selling_url=item.selling_url,
            selling_price=item.selling_price,
            price_difference=item.price_difference,
            estimated_profit=item.estimated_profit,
            profit_margin=item.profit_margin,
            demand_score=item.demand_score,
            turnover_score=item.turnover_score,
            arbitrage_score=item.arbitrage_score,
            recommendation_rank=index,
            decision=item.decision,
            external_id=item.external_id,
            market_source=item.market_source,
            condition=item.condition,
            listing_url=item.listing_url,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _rank_key(item: ArbitrageOpportunity) -> tuple[float, float, float, float, str]:
    return (
        -item.arbitrage_score,
        -item.demand_score,
        -float(item.estimated_profit),
        -item.turnover_score,
        item.external_id,
    )
