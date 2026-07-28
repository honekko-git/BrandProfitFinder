"""
Marketplace listing validation helpers.
"""

import logging
from decimal import Decimal
from urllib.parse import urlparse

from config.constants import MARKETPLACE_AMAZON_JP, MARKETPLACE_RAKUTEN
from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)

MAX_SELLER_RATING = Decimal("5.0")


def validate_listing(listing: MarketplaceListing) -> tuple[bool, str]:
    """
    Validate one marketplace listing.

    Args:
        listing: Listing to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not listing.title or not listing.title.strip():
        return False, "missing listing title"

    if not listing.marketplace_name or not listing.marketplace_name.strip():
        return False, "missing marketplace name"

    if listing.price_jpy <= 0:
        return False, "price_jpy must be greater than zero"

    if listing.marketplace_name in {MARKETPLACE_AMAZON_JP, MARKETPLACE_RAKUTEN}:
        if not listing.listing_url.strip() and not listing.listing_id.strip():
            label = "ASIN" if listing.marketplace_name == MARKETPLACE_AMAZON_JP else "itemCode"
            return False, f"missing listing URL or {label}"

    total = listing.total_price_jpy or listing.compute_total_price_jpy()
    if total <= 0:
        return False, "total_price_jpy must be greater than zero"

    if listing.shipping_jpy is not None and listing.shipping_jpy < 0:
        return False, "shipping_jpy must not be negative"

    if listing.listing_url and not _is_valid_url(listing.listing_url):
        return False, f"invalid listing URL: {listing.listing_url}"

    if listing.seller_rating is not None:
        if listing.seller_rating < 0 or listing.seller_rating > MAX_SELLER_RATING:
            return False, "seller_rating out of allowed range"

    if listing.sold_count is not None and listing.sold_count < 0:
        return False, "sold_count must not be negative"

    return True, ""


def validate_listings(
    listings: list[MarketplaceListing],
) -> tuple[list[MarketplaceListing], list[MarketplaceListing]]:
    """
    Split listings into valid and rejected groups.

    Args:
        listings: Candidate listings. Not modified.

    Returns:
        Tuple of (valid_listings, rejected_listings).
    """
    valid: list[MarketplaceListing] = []
    rejected: list[MarketplaceListing] = []

    for listing in listings:
        is_valid, reason = validate_listing(listing)
        checked = MarketplaceListing(
            marketplace_name=listing.marketplace_name,
            listing_id=listing.listing_id,
            title=listing.title,
            brand=listing.brand,
            model_number=listing.model_number,
            sku=listing.sku,
            jan_code=listing.jan_code,
            condition=listing.condition,
            price_jpy=listing.price_jpy,
            shipping_jpy=listing.shipping_jpy,
            total_price_jpy=listing.total_price_jpy,
            seller_name=listing.seller_name,
            seller_rating=listing.seller_rating,
            listing_url=listing.listing_url,
            image_url=listing.image_url,
            availability=listing.availability,
            sold_count=listing.sold_count,
            source_query=listing.source_query,
            matched_product_id=listing.matched_product_id,
            match_score=listing.match_score,
            is_valid=is_valid,
            validation_error=reason,
            currency=listing.currency,
            points_jpy=listing.points_jpy,
            is_prime=listing.is_prime,
            is_amazon_seller=listing.is_amazon_seller,
            shipping_unknown=listing.shipping_unknown,
            point_rate=listing.point_rate,
            source_metadata=dict(listing.source_metadata),
        )
        if is_valid:
            valid.append(checked)
        else:
            logger.warning(
                "Rejected listing %r from %s: %s",
                listing.title,
                listing.marketplace_name,
                reason,
            )
            rejected.append(checked)

    return valid, rejected


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
