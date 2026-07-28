"""
Product-to-listing matching helpers.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from config.constants import (
    MARKETPLACE_CHRONO24,
    MARKETPLACE_FARFETCH,
    MARKETPLACE_FASHIONPHILE,
    MARKETPLACE_GRAILED,
    MARKETPLACE_THEREALREAL,
    MARKETPLACE_USED_DEMO,
    MARKETPLACE_VESTIAIRE,
    MARKETPLACE_YAHOO_AUCTION,
)
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
    style_score: Decimal = Decimal("27")
    reference_score: Decimal = Decimal("28")
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
        listing_reference = _normalize_text(
            str(listing.source_metadata.get("source_reference_number") or "")
        )
        listing_style = _normalize_text(str(listing.source_metadata.get("source_style_code") or ""))
        listing_jan_meta = _normalize_text(str(listing.source_metadata.get("source_jan") or ""))

        if listing_jan and (product_sku == listing_jan or product_model == listing_jan):
            total += self.config.jan_score
        elif listing_jan_meta and (product_sku == listing_jan_meta or product_model == listing_jan_meta):
            total += self.config.jan_score
        elif listing.jan_code and (
            product_sku == _normalize_text(listing.jan_code)
            or product_model == _normalize_text(listing.jan_code)
        ):
            total += self.config.jan_score

        if product_sku and listing_sku and product_sku == listing_sku:
            total += self.config.sku_score
        elif (
            product_sku
            and listing.listing_id
            and listing.marketplace_name not in {
                MARKETPLACE_YAHOO_AUCTION,
                MARKETPLACE_USED_DEMO,
                MARKETPLACE_VESTIAIRE,
                MARKETPLACE_FASHIONPHILE,
                MARKETPLACE_THEREALREAL,
                MARKETPLACE_GRAILED,
                MARKETPLACE_CHRONO24,
                MARKETPLACE_FARFETCH,
            }
            and product_sku == _normalize_text(listing.listing_id)
        ):
            total += self.config.sku_score

        if product_model and listing_model and product_model == listing_model:
            total += self.config.model_score
        elif product_model and listing_style and product_model == listing_style:
            total += self.config.style_score
        elif product_model and listing_reference and product_model == listing_reference:
            total += self.config.reference_score

        product_brand = _normalize_text(product.brand)
        listing_brand = _normalize_text(listing.brand)
        if product_brand and listing_brand and product_brand == listing_brand:
            total += self.config.brand_score

        title_score = _title_overlap_score(product.name, listing.title, self.config.title_word_score)
        total += title_score

        return min(total, Decimal("100"))

    def get_comparison_warnings(self, product: Product, listing: MarketplaceListing) -> list[str]:
        """
        Return non-blocking warnings for attribute differences after identity match.

        Condition, accessories, and authentication are not used for identity matching.

        Args:
            product: Overseas product.
            listing: Domestic listing candidate.

        Returns:
            Warning messages for color, size, or model differences.
        """
        warnings: list[str] = []
        product_name = _normalize_text(product.name)
        title = _normalize_text(listing.title)

        color_tokens = {"black", "white", "red", "blue", "brown", "pink", "gold", "silver", "beige", "green"}
        product_colors = color_tokens & set(_tokenize(product.name))
        title_colors = color_tokens & set(_tokenize(listing.title))
        if product_colors and title_colors and product_colors != title_colors:
            warnings.append("color mismatch between product and listing title")

        size_pattern = re.compile(r"\b(\d{2}|xs|s|m|l|xl|xxl|one\s*size)\b", re.IGNORECASE)
        product_sizes = set(size_pattern.findall(product.name.lower()))
        title_sizes = set(size_pattern.findall(listing.title.lower()))
        if product_sizes and title_sizes and product_sizes != title_sizes:
            warnings.append("size mismatch between product and listing title")

        if product.model and listing.model_number:
            if _normalize_text(product.model) != _normalize_text(listing.model_number):
                warnings.append("model number differs from listing")

        if listing.marketplace_name == MARKETPLACE_CHRONO24:
            meta = listing.source_metadata
            product_diameter = _extract_case_diameter_mm(product.name)
            listing_diameter = meta.get("source_case_diameter_mm")
            if product_diameter and listing_diameter and product_diameter != listing_diameter:
                warnings.append("case diameter mismatch between product and listing")

            product_dial = _normalize_text(_extract_dial_color(product.name))
            listing_dial = _normalize_text(str(meta.get("source_dial_color") or ""))
            if product_dial and listing_dial and product_dial != listing_dial:
                warnings.append("dial color mismatch between product and listing")

            product_bracelet = _normalize_text(_extract_bracelet_material(product.name))
            listing_bracelet = _normalize_text(str(meta.get("source_bracelet_material") or ""))
            if product_bracelet and listing_bracelet and product_bracelet != listing_bracelet:
                warnings.append("bracelet material mismatch between product and listing")

        if listing.marketplace_name == MARKETPLACE_FARFETCH:
            meta = listing.source_metadata
            product_material = _normalize_text(_extract_material(product.name))
            listing_material = _normalize_text(str(meta.get("source_material") or ""))
            if product_material and listing_material and product_material != listing_material:
                warnings.append("material mismatch between product and listing")

            product_gender = _normalize_text(_extract_gender(product.name))
            listing_gender = _normalize_text(str(meta.get("source_gender") or ""))
            if product_gender and listing_gender and product_gender != listing_gender:
                warnings.append("gender mismatch between product and listing")

        if listing.used_item_details is not None:
            auth_status = listing.used_item_details.authentication.status.value
            if auth_status.endswith("CLAIM"):
                warnings.append("authentication based on seller claim only")

        return warnings

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
                    used_item_details=listing.used_item_details,
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


def _extract_case_diameter_mm(text: str) -> float | None:
    match = re.search(r"(\d{2}(?:\.\d+)?)\s*mm", text.lower())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_dial_color(text: str) -> str:
    colors = {"black", "white", "blue", "green", "silver", "gold", "grey", "gray", "brown"}
    tokens = set(_tokenize(text))
    found = colors & tokens
    return next(iter(found), "")


def _extract_bracelet_material(text: str) -> str:
    materials = {
        "steel": "STAINLESS_STEEL",
        "stainless": "STAINLESS_STEEL",
        "leather": "LEATHER",
        "rubber": "RUBBER",
        "titanium": "TITANIUM",
        "gold": "GOLD",
    }
    lowered = text.lower()
    for key, value in materials.items():
        if key in lowered:
            return value
    return ""


def _extract_material(text: str) -> str:
    materials = {"leather", "canvas", "cotton", "wool", "silk", "nylon", "suede"}
    tokens = set(_tokenize(text))
    found = materials & tokens
    return next(iter(found), "")


def _extract_gender(text: str) -> str:
    lowered = text.lower()
    if "women" in lowered or "woman" in lowered:
        return "women"
    if "men" in lowered and "women" not in lowered:
        return "men"
    if "unisex" in lowered:
        return "unisex"
    return ""
