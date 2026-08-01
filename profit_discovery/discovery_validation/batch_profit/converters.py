"""Converters between batch candidates and existing marketplace models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus
from marketplace.connectors.models import MarketListing
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate


def candidate_to_market_listing(candidate: BatchProfitCandidate) -> MarketListing:
    """Convert one batch candidate to MarketListing for Yahoo live resolution."""
    return MarketListing(
        id=candidate.candidate_id,
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
        condition=candidate.condition,
        price=candidate.purchase_price,
        currency=candidate.currency,
        market_name=candidate.purchase_source,
        url=candidate.purchase_url,
        source_type="IMPORT",
        created_at=datetime.now(tz=UTC),
    )


def candidate_to_acquired_listing(candidate: BatchProfitCandidate) -> AcquiredListing:
    """Convert one batch candidate to AcquiredListing for comparable matching."""
    return AcquiredListing(
        external_id=candidate.candidate_id,
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
        condition=candidate.condition,
        price=candidate.purchase_price,
        currency=candidate.currency,
        url=candidate.purchase_url,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source=candidate.purchase_source,
        raw_title=candidate.title,
        acquisition_status=AcquisitionStatus.LIVE,
    )
