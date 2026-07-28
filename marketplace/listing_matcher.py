"""
Product-to-listing matching helpers.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from config.constants import MARKETPLACE_YAHOO_AUCTION
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from marketplace.listing_validator import validate_listing

logger = logging.getLogger(__name__)


@dataclass
class MatchConfig:
    """Configurable weights for listing match scoring."""

    jan_score: Decimal = Decimal("40")
    sku_score: Decimal = Decimal("35")
    model_score: Decimal = Decimal("30")
    brand_score: Decimal = Decimal("15")
    title_word_score: Decimal = Decimal("20")
    match_threshold: Decimal = Decimal("30")


class ListingMatcher:
    """Score and rank marketplace listings against overseas products."""

    def __init__(self, config: MatchConfig | None = None) -> None:
        """
        Initialize matcher with optional score weights.

        Args:
            config: Match scoring configuration.
        """
        self.config = config or MatchConfig()

    def score(self, product: Product, listing: MarketplaceListing) -> Decimal:
        """
        Calculate match score between a product and listing.

        Args:
            product: Overseas product.
            listing: Domestic listing candidate.

        Returns:
            Match score between 0 and 100.
        """
        total = Decimal("0")

        product_sku = _normalize_text(product.sku)
        listing_sku = _normalize_text(listing.sku)
        listing_jan = _normalize_text(listing.jan_code)
        product_model = _normalize_text(product.model)
        listing_model = _normalize_text(listing.model_number)

        if listing_jan and (product_sku == listing_jan or product_model == listing_jan):
            total += self.config.jan_score

        if product_sku and listing_sku and product_sku == listing_sku:
            total += self.config.sku_score
        elif (
            product_sku
            and listing.listing_id
            and listing.marketplace_name != MARKETPLACE_YAHOO_AUCTION
            and product_sku == _normalize_text(listing.listing_id)
        ):
            total += self.config.sku_score

        if product_model and listing_model and product_model == listing_model:
            total += self.config.model_score

        product_brand = _normalize_text(product.brand)
        listing_brand = _normalize_text(listing.brand)
        if product_brand and listing_brand and product_brand == listing_brand:
            total += self.config.brand_score

        title_score = _title_overlap_score(product.name, listing.title, self.config.title_word_score)
        total += title_score

        return min(total, Decimal("100"))

    def is_match(
        self,
        product: Product,
        listing: MarketplaceListing,
        threshold: Decimal | None = None,
    ) -> bool:
        """
        Check whether listing score meets threshold.

        Args:
            product: Overseas product.
            listing: Domestic listing candidate.
            threshold: Minimum score. Uses config default when None.

        Returns:
            True when score meets threshold.
        """
        minimum = threshold if threshold is not None else self.config.match_threshold
        return self.score(product, listing) >= minimum

    def match_and_rank(
        self,
        product: Product,
        listings: list[MarketplaceListing],
        exclude_invalid: bool = True,
    ) -> list[MarketplaceListing]:
        """
        Score listings and return ranked copies.

        Args:
            product: Overseas product.
            listings: Candidate listings. Not modified.
            exclude_invalid: Skip listings that fail validation when True.

        Returns:
            Ranked listing copies with match_score populated.
        """
        ranked: list[MarketplaceListing] = []

        for listing in listings:
            if exclude_invalid:
                is_valid, _ = validate_listing(listing)
                if not is_valid:
                    continue

            match_score = self.score(product, listing)
            ranked.append(
                MarketplaceListing(
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
                    matched_product_id=product.sku or product.name,
                    match_score=match_score,
                    is_valid=listing.is_valid,
                    validation_error=listing.validation_error,
                    currency=listing.currency,
                    points_jpy=listing.points_jpy,
                    is_prime=listing.is_prime,
                    is_amazon_seller=listing.is_amazon_seller,
                    shipping_unknown=listing.shipping_unknown,
                    point_rate=listing.point_rate,
                    source_metadata=dict(listing.source_metadata),
                )
            )

        ranked.sort(
            key=lambda item: (-item.match_score, item.title, item.listing_id),
        )
        return ranked


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value.strip().lower())
    normalized = re.sub(r"[\s\-_/]+", "", normalized)
    return normalized


def _title_overlap_score(product_name: str, listing_title: str, max_score: Decimal) -> Decimal:
    product_words = set(_tokenize(product_name))
    title_words = set(_tokenize(listing_title))
    if not product_words or not title_words:
        return Decimal("0")

    overlap = product_words & title_words
    ratio = Decimal(str(len(overlap))) / Decimal(str(len(product_words)))
    return (ratio * max_score).quantize(Decimal("0.01"))


def _tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text.lower())
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return [token for token in normalized.split() if token]
