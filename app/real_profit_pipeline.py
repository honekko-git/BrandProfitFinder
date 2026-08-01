"""Browser pipeline for single-route real profit verification."""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.connectors.models import MarketListing
from marketplace.importers.manual_importer import ManualImporter
from profit_discovery.discovery_validation.real_profit_models import RealProfitVerificationResult
from profit_discovery.discovery_validation.real_profit_verification import (
    build_real_profit_verifications,
    is_real_route_brand,
    is_real_route_category,
    real_profit_to_validation_opportunity,
)

from app.store import ValidationResultStore, ValidationSearchSnapshot


@dataclass(frozen=True, slots=True)
class RealProfitPipelineResult:
    """Output from one real profit verification search."""

    snapshot: ValidationSearchSnapshot
    real_results: list[RealProfitVerificationResult]
    validation_count: int


def run_real_profit_verification_search(
    *,
    brand: str,
    category: str,
    yahoo_transport: object | None = None,
    manual_purchase_url: str = "",
    manual_purchase_title: str = "",
    manual_purchase_price: str = "",
    manual_purchase_currency: str = "USD",
) -> RealProfitPipelineResult:
    """Run the Fashionphile -> Yahoo Auction real profit verification route."""
    normalized_brand = brand.strip()
    normalized_category = category.strip()
    if not is_real_route_brand(normalized_brand):
        raise ValueError(f"Real route supports brands only: Chanel, Louis Vuitton")
    if not is_real_route_category(normalized_category):
        raise ValueError("Real route supports category only: Wallet")

    manual_listing = _build_manual_listing(
        brand=normalized_brand,
        category=normalized_category,
        title=manual_purchase_title,
        url=manual_purchase_url,
        price=manual_purchase_price,
        currency=manual_purchase_currency,
    )
    real_results = build_real_profit_verifications(
        brand=normalized_brand,
        category=normalized_category,
        manual_listing=manual_listing,
        yahoo_transport=yahoo_transport,
    )
    validation_ranking = [real_profit_to_validation_opportunity(item) for item in real_results]
    snapshot = ValidationSearchSnapshot(
        brand=normalized_brand,
        category=normalized_category,
        market_mode="REAL",
        validation_ranking=validation_ranking,
        candidates_by_id={},
        real_profit_results=real_results,
        verification_mode="REAL",
    )
    return RealProfitPipelineResult(
        snapshot=snapshot,
        real_results=real_results,
        validation_count=len(real_results),
    )


def execute_real_profit_verification_search(
    store: ValidationResultStore,
    *,
    brand: str,
    category: str,
    yahoo_transport: object | None = None,
    manual_purchase_url: str = "",
    manual_purchase_title: str = "",
    manual_purchase_price: str = "",
    manual_purchase_currency: str = "USD",
) -> RealProfitPipelineResult:
    """Execute real profit verification and persist snapshot."""
    result = run_real_profit_verification_search(
        brand=brand,
        category=category,
        yahoo_transport=yahoo_transport,
        manual_purchase_url=manual_purchase_url,
        manual_purchase_title=manual_purchase_title,
        manual_purchase_price=manual_purchase_price,
        manual_purchase_currency=manual_purchase_currency,
    )
    store.save(result.snapshot)
    return result


def _build_manual_listing(
    *,
    brand: str,
    category: str,
    title: str,
    url: str,
    price: str,
    currency: str,
) -> MarketListing | None:
    if not url.strip() or not price.strip():
        return None
    listing_title = title.strip() or f"{brand} {category}".strip()
    return ManualImporter().create_listing(
        title=listing_title,
        brand=brand,
        category=category,
        condition="Used",
        price=price,
        currency=currency,
        market_name="Fashionphile",
        url=url.strip(),
    )
