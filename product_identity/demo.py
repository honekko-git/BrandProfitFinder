"""Run Phase 19 identity demo pairs from synthetic fixtures."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path

from models.marketplace_listing import MarketplaceListing
from models.product import Product
from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityDecision

logger = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "product_identity_phase19.json"


def run_identity_demo() -> dict[str, int]:
    """Evaluate synthetic identity fixture pairs and return summary counts."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    service = ProductIdentityService()
    counts = {
        "total": 0,
        IdentityDecision.MATCH.value: 0,
        IdentityDecision.REVIEW.value: 0,
        IdentityDecision.NO_MATCH.value: 0,
        IdentityDecision.INSUFFICIENT_DATA.value: 0,
        "hard_conflict": 0,
        "review_required": 0,
    }
    for item in payload["pairs"]:
        product = Product(**item["product"])
        listing_data = dict(item["listing"])
        meta = listing_data.pop("source_metadata", {})
        price = Decimal(str(listing_data.pop("price_jpy", 0)))
        listing = MarketplaceListing(
            **listing_data,
            price_jpy=price,
            source_metadata=meta,
        )
        result = service.evaluate_product_listing(product, listing)
        counts["total"] += 1
        counts[result.decision.value] += 1
        if result.hard_conflict:
            counts["hard_conflict"] += 1
        if result.review_required:
            counts["review_required"] += 1
    logger.info(
        "Identity demo summary (synthetic fixtures): total=%d match=%d review=%d no_match=%d insufficient=%d hard_conflict=%d review_required=%d",
        counts["total"],
        counts[IdentityDecision.MATCH.value],
        counts[IdentityDecision.REVIEW.value],
        counts[IdentityDecision.NO_MATCH.value],
        counts[IdentityDecision.INSUFFICIENT_DATA.value],
        counts["hard_conflict"],
        counts["review_required"],
    )
    return counts
