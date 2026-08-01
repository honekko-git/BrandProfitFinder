"""Convert discovery results into persisted opportunity records."""

from __future__ import annotations

from datetime import UTC, datetime

from app.storage.models import OpportunityRecord, OpportunityStatus
from profit_discovery.arbitrage.models import ArbitrageOpportunity


def opportunity_record_from_arbitrage(item: ArbitrageOpportunity) -> OpportunityRecord:
    """Build one OpportunityRecord from an arbitrage ranking item."""
    now = datetime.now(tz=UTC)
    return OpportunityRecord(
        id=None,
        product_name=item.product,
        brand=item.brand,
        category=item.category,
        purchase_source=item.purchase_source,
        purchase_url=item.purchase_url,
        purchase_price=float(item.purchase_price),
        selling_market=item.selling_market,
        selling_url=item.selling_url,
        selling_price=float(item.selling_price),
        estimated_profit=float(item.estimated_profit),
        profit_margin=float(item.profit_margin),
        demand_score=item.demand_score,
        turnover_score=item.turnover_score,
        arbitrage_score=item.arbitrage_score,
        decision=item.decision,
        status=OpportunityStatus.NEW,
        created_at=now,
        updated_at=now,
    )
