"""Ranking helpers for profit validation opportunities."""

from __future__ import annotations

from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.discovery_validation.models import ValidationConfig, ValidationOpportunity
from profit_discovery.discovery_validation.validator import ProfitValidationValidator
from marketplace.connectors.models import MarketListing


def create_validation_ranking(
    arbitrage_opportunities: list[ArbitrageOpportunity]
    | tuple[ArbitrageOpportunity, ...],
    *,
    config: ValidationConfig | None = None,
    validator: ProfitValidationValidator | None = None,
    selling_listings_by_id: dict[str, MarketListing] | None = None,
) -> list[ValidationOpportunity]:
    """Build a ranked profit validation list from arbitrage opportunities."""
    active_config = config or ValidationConfig()
    active_validator = validator or ProfitValidationValidator(config=active_config)
    listings = selling_listings_by_id or {}

    resolved: list[ValidationOpportunity] = []
    for item in arbitrage_opportunities:
        if not active_config.is_allowed_brand(item.brand):
            continue
        if not active_config.is_allowed_category(item.category):
            continue
        base = validation_opportunity_from_arbitrage(
            item,
            selling_listing=listings.get(item.external_id),
        )
        resolved.append(active_validator.validate_one(base))

    ranked = sorted(resolved, key=_rank_key)
    return [
        ValidationOpportunity(
            product=item.product,
            brand=item.brand,
            category=item.category,
            purchase_source=item.purchase_source,
            purchase_price=item.purchase_price,
            purchase_url=item.purchase_url,
            domestic_market=item.domestic_market,
            domestic_price=item.domestic_price,
            domestic_url=item.domestic_url,
            estimated_profit=item.estimated_profit,
            profit_margin=item.profit_margin,
            demand_score=item.demand_score,
            turnover_score=item.turnover_score,
            validation_score=item.validation_score,
            decision=item.decision,
            external_id=item.external_id,
            recommendation_rank=index,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def validation_opportunity_from_arbitrage(
    item: ArbitrageOpportunity,
    *,
    selling_listing: MarketListing | None = None,
) -> ValidationOpportunity:
    """Map one arbitrage opportunity into a validation candidate."""
    domestic_market = item.selling_market
    domestic_price = item.selling_price
    domestic_url = item.selling_url
    if selling_listing is not None:
        domestic_market = selling_listing.market_name or domestic_market
        domestic_price = selling_listing.price
        domestic_url = selling_listing.url or domestic_url

    return ValidationOpportunity(
        product=item.product,
        brand=item.brand,
        category=item.category,
        purchase_source=item.purchase_source,
        purchase_price=item.purchase_price,
        purchase_url=item.purchase_url,
        domestic_market=domestic_market,
        domestic_price=domestic_price,
        domestic_url=domestic_url,
        estimated_profit=item.estimated_profit,
        profit_margin=item.profit_margin,
        demand_score=item.demand_score,
        turnover_score=item.turnover_score,
        validation_score=0.0,
        decision="N/A",
        external_id=item.external_id,
    )


def validation_opportunity_to_arbitrage(item: ValidationOpportunity) -> ArbitrageOpportunity:
    """Convert one validation opportunity back into an arbitrage opportunity for SQLite save."""
    from profit_discovery.arbitrage.models import ArbitrageOpportunity

    return ArbitrageOpportunity(
        product=item.product,
        brand=item.brand,
        category=item.category,
        purchase_source=item.purchase_source,
        purchase_url=item.purchase_url,
        purchase_price=item.purchase_price,
        selling_market=item.domestic_market,
        selling_url=item.domestic_url,
        selling_price=item.domestic_price,
        price_difference=item.domestic_price - item.purchase_price,
        estimated_profit=item.estimated_profit,
        profit_margin=item.profit_margin,
        demand_score=item.demand_score,
        turnover_score=item.turnover_score,
        arbitrage_score=item.validation_score,
        recommendation_rank=item.recommendation_rank,
        decision=item.decision,
        external_id=item.external_id,
        market_source=item.purchase_source,
        condition="",
        listing_url=item.purchase_url,
    )


def _rank_key(item: ValidationOpportunity) -> tuple[float, float, float, float, str]:
    return (
        -item.validation_score,
        -item.demand_score,
        -float(item.estimated_profit),
        -item.turnover_score,
        item.external_id,
    )
