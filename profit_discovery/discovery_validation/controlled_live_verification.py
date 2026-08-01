"""Controlled live profit verification pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote_plus

from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.fashionphile_acquirer import (
    FashionphileAcquirer,
    acquired_listing_to_market_listing,
)
from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.matching import (
    build_yahoo_search_terms,
)
from marketplace.browser_acquisition.models import (
    AcquiredListing,
    AcquisitionResult,
    AcquisitionStatus,
    ControlledLiveVerificationResult,
    ReliabilityLevel,
)
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer
from marketplace.importers.converters import market_listing_to_supplier_product
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_validation.models import ValidationOpportunity
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate
from profit_discovery.discovery_validation.real_profit_models import DataStatus
from profit_discovery.discovery_validation.validator import ProfitValidationValidator
from profit_discovery.models import BuyDecision
from profit_intelligence.discovery_engine import DiscoveryEngine
from profit_intelligence.normalization import clamp_score
from supplier.models import to_product_candidate

NOT_CONFIGURED = "Not configured"
PROVISIONAL_PREFIX = "PROVISIONAL "


def build_controlled_live_verifications(
    *,
    brand: str = "Chanel",
    category: str = "Wallet",
    purchase_limit: int = 10,
    sold_limit: int = 20,
    exchange_rate: float | None = None,
    purchase_html: str | None = None,
    yahoo_html_by_query: dict[str, str] | None = None,
    fashionphile_acquirer: FashionphileAcquirer | None = None,
    yahoo_acquirer: YahooSoldAcquirer | None = None,
) -> tuple[list[ControlledLiveVerificationResult], str]:
    """Run one controlled live check without silent fixture fallback."""
    if brand.strip().lower() != "chanel":
        raise ValueError("Controlled live route supports brand only: Chanel")
    if category.strip().lower() != "wallet":
        raise ValueError("Controlled live route supports category only: Wallet")

    active_rate = exchange_rate if exchange_rate is not None else resolve_usd_jpy_exchange_rate()
    fp_acquirer = fashionphile_acquirer or FashionphileAcquirer(purchase_limit=purchase_limit)
    yh_acquirer = yahoo_acquirer or YahooSoldAcquirer(sold_limit=sold_limit)

    try:
        purchase_result = fp_acquirer.acquire(
            brand=brand,
            category=category,
            html=purchase_html,
        )
    except AcquisitionBlockedError as exc:
        return [], exc.reason.value

    if purchase_result.status == AcquisitionStatus.BLOCKED:
        return [], purchase_result.blocking_reason or BlockingReason.NO_RESULTS.value
    if not purchase_result.listings:
        return [], purchase_result.blocking_reason or BlockingReason.NO_RESULTS.value

    results: list[ControlledLiveVerificationResult] = []
    for index, listing in enumerate(purchase_result.listings, start=1):
        result = _verify_one_listing(
            listing=listing,
            brand=brand,
            category=category,
            active_rate=active_rate,
            purchase_result=purchase_result,
            yh_acquirer=yh_acquirer,
            yahoo_html_by_query=yahoo_html_by_query or {},
            rank=index,
        )
        results.append(result)

    ranked = sorted(
        results,
        key=lambda item: (-item.validation_score, -float(item.estimated_profit), item.external_id),
    )
    return [
        ControlledLiveVerificationResult(
            product=item.product,
            brand=item.brand,
            category=item.category,
            fashionphile_url=item.fashionphile_url,
            purchase_price=item.purchase_price,
            purchase_currency=item.purchase_currency,
            purchase_price_jpy_estimate=item.purchase_price_jpy_estimate,
            exchange_rate_display=item.exchange_rate_display,
            yahoo_search_terms=item.yahoo_search_terms,
            yahoo_sold_samples=item.yahoo_sold_samples,
            yahoo_matched_samples=item.yahoo_matched_samples,
            matching_score=item.matching_score,
            matching_reliability=item.matching_reliability,
            median_selling_price_jpy=item.median_selling_price_jpy,
            average_selling_price_jpy=item.average_selling_price_jpy,
            cost_configuration_status=item.cost_configuration_status,
            estimated_shipping=item.estimated_shipping,
            estimated_import_cost=item.estimated_import_cost,
            estimated_profit=item.estimated_profit,
            profit_margin=item.profit_margin,
            roi=item.roi,
            demand_score=item.demand_score,
            turnover_score=item.turnover_score,
            validation_score=item.validation_score,
            decision=item.decision,
            acquisition_status=item.acquisition_status,
            data_status=item.data_status,
            verification_complete=item.verification_complete,
            retrieved_at=item.retrieved_at,
            external_id=item.external_id,
            blocking_reason=item.blocking_reason,
            recommendation_rank=rank,
        )
        for rank, item in enumerate(ranked, start=1)
    ], ""


def _verify_one_listing(
    *,
    listing: AcquiredListing,
    brand: str,
    category: str,
    active_rate: float,
    purchase_result: AcquisitionResult,
    yh_acquirer: YahooSoldAcquirer,
    yahoo_html_by_query: dict[str, str],
    rank: int,
) -> ControlledLiveVerificationResult:
    search_terms = build_yahoo_search_terms(title=listing.title, brand=brand, category=category)
    yahoo_html = yahoo_html_by_query.get(search_terms)
    purchase_live = purchase_result.status == AcquisitionStatus.LIVE

    try:
        yahoo_result = yh_acquirer.acquire(search_terms=search_terms, html=yahoo_html)
    except AcquisitionBlockedError as exc:
        yahoo_result = AcquisitionResult(
            status=AcquisitionStatus.BLOCKED,
            blocking_reason=exc.reason.value,
            detail=exc.detail,
            search_query=search_terms,
            source="Yahoo Auction",
        )

    purchase_jpy = listing.price * Decimal(str(active_rate)) if listing.currency.upper() != "JPY" else listing.price
    comparable = evaluate_comparables(
        listing,
        list(yahoo_result.samples),
        purchase_price_jpy=purchase_jpy,
    )
    domestic_live = yahoo_result.status == AcquisitionStatus.LIVE and comparable.sample_count > 0

    supplier_product = market_listing_to_supplier_product(acquired_listing_to_market_listing(listing))
    candidate = to_product_candidate(supplier_product)
    product = Product(
        name=str(candidate["name"]),
        brand=str(candidate["brand"]),
        price=float(candidate["purchase_price"]),
        currency=str(candidate["currency"]),
        store_name=str(candidate["source"]),
        url=str(candidate.get("url") or ""),
        model=str(candidate.get("model_number") or ""),
        exchange_rate=active_rate,
    )

    selling_price = comparable.median_jpy if comparable.sample_count > 0 else Decimal("0")
    profit_result = ProfitCalculator().calculate(
        product,
        selling_price,
        domestic_market="yahoo_auction",
    )
    discovery_score = DiscoveryEngine().score(profit_result)
    buy_decision = BuyDecisionEngine().decide(profit_result, discovery_score)

    purchase_jpy = profit_result.purchase_price_jpy or purchase_jpy
    validation_base = ValidationOpportunity(
        product=listing.title,
        brand=listing.brand or brand,
        category=listing.category or category,
        purchase_source=listing.source,
        purchase_price=purchase_jpy,
        purchase_url=listing.url,
        domestic_market="Yahoo Auction",
        domestic_price=selling_price,
        domestic_url=_yahoo_search_url(search_terms),
        estimated_profit=profit_result.profit_jpy,
        profit_margin=profit_result.profit_margin,
        demand_score=clamp_score(comparable.sample_count * 12.0),
        turnover_score=clamp_score(comparable.sample_count * 10.0),
        validation_score=0.0,
        decision=buy_decision.decision.value,
        external_id=listing.external_id,
    )
    validated = ProfitValidationValidator().validate_one(validation_base)

    costs_configured = _costs_configured(profit_result)
    provisional = (
        not costs_configured
        or comparable.reliability == ReliabilityLevel.LOW
        or comparable.sample_count < 3
    )
    decision = _apply_provisional_label(validated.decision, provisional)

    data_status = _resolve_data_status(
        purchase_live=purchase_live,
        domestic_live=domestic_live,
        purchase_status=purchase_result.status.value,
        domestic_status=yahoo_result.status.value,
    )
    acquisition_status = _resolve_acquisition_status(purchase_result, yahoo_result, comparable.sample_count)
    verification_complete = (
        data_status == DataStatus.LIVE.value
        and comparable.sample_count >= 3
        and costs_configured
        and not provisional
    )

    blocking_reason = ""
    if yahoo_result.blocking_reason:
        blocking_reason = yahoo_result.blocking_reason
    elif comparable.sample_count == 0 and yahoo_result.status == AcquisitionStatus.LIVE:
        blocking_reason = BlockingReason.SOLD_PRICE_NOT_AVAILABLE.value

    best_score = 0.0
    if comparable.accepted_diagnostics:
        best_score = float(max(item.matching_score for item in comparable.accepted_diagnostics))

    return ControlledLiveVerificationResult(
        product=listing.title,
        brand=listing.brand or brand,
        category=listing.category or category,
        fashionphile_url=listing.url,
        purchase_price=listing.price,
        purchase_currency=listing.currency,
        purchase_price_jpy_estimate=purchase_jpy,
        exchange_rate_display=(
            f"{active_rate:g} JPY/USD"
            if listing.currency.upper() != "JPY"
            else "Not required (JPY)"
        ),
        yahoo_search_terms=search_terms,
        yahoo_sold_samples=len(yahoo_result.samples),
        yahoo_matched_samples=comparable.sample_count,
        matching_score=best_score,
        matching_reliability=comparable.reliability.value,
        median_selling_price_jpy=comparable.median_jpy,
        average_selling_price_jpy=comparable.average_jpy,
        cost_configuration_status="Configured" if costs_configured else "Not configured",
        estimated_shipping=_format_optional_jpy(profit_result.international_shipping_jpy),
        estimated_import_cost=_format_optional_jpy(
            profit_result.customs_duty_jpy
            + profit_result.import_tax_jpy
            + profit_result.other_costs_jpy
        ),
        estimated_profit=profit_result.profit_jpy,
        profit_margin=profit_result.profit_margin,
        roi=profit_result.roi,
        demand_score=validated.demand_score,
        turnover_score=validated.turnover_score,
        validation_score=validated.validation_score,
        decision=decision,
        acquisition_status=acquisition_status,
        data_status=data_status,
        verification_complete=verification_complete,
        retrieved_at=listing.retrieved_at,
        external_id=listing.external_id,
        blocking_reason=blocking_reason,
        recommendation_rank=rank,
    )


def _apply_provisional_label(decision: str, provisional: bool) -> str:
    if not provisional:
        return decision
    if decision.startswith(PROVISIONAL_PREFIX):
        return decision
    return f"{PROVISIONAL_PREFIX}{decision}"


def _costs_configured(profit_result) -> bool:
    shipping = profit_result.international_shipping_jpy or Decimal("0")
    import_cost = (
        (profit_result.customs_duty_jpy or Decimal("0"))
        + (profit_result.import_tax_jpy or Decimal("0"))
        + (profit_result.other_costs_jpy or Decimal("0"))
    )
    return shipping > 0 or import_cost > 0


def _format_optional_jpy(value: Decimal) -> str:
    if value is None or value <= 0:
        return NOT_CONFIGURED
    return f"{int(value):,} JPY"


def _resolve_data_status(
    *,
    purchase_live: bool,
    domestic_live: bool,
    purchase_status: str,
    domestic_status: str,
) -> str:
    if purchase_live and domestic_live:
        return DataStatus.LIVE.value
    if purchase_status == AcquisitionStatus.BLOCKED.value or domestic_status == AcquisitionStatus.BLOCKED.value:
        return DataStatus.UNAVAILABLE.value
    if purchase_live or domestic_live:
        return DataStatus.MIXED.value
    if purchase_status == AcquisitionStatus.PARTIAL.value or domestic_status == AcquisitionStatus.PARTIAL.value:
        return DataStatus.MIXED.value
    return DataStatus.UNAVAILABLE.value


def _resolve_acquisition_status(
    purchase_result: AcquisitionResult,
    yahoo_result: AcquisitionResult,
    matched_count: int,
) -> str:
    if purchase_result.status == AcquisitionStatus.LIVE and yahoo_result.status == AcquisitionStatus.LIVE:
        if matched_count >= 3:
            return AcquisitionStatus.LIVE.value
        return AcquisitionStatus.PARTIAL.value
    if purchase_result.status == AcquisitionStatus.BLOCKED or yahoo_result.status == AcquisitionStatus.BLOCKED:
        return AcquisitionStatus.BLOCKED.value
    return AcquisitionStatus.PARTIAL.value


def _yahoo_search_url(keyword: str) -> str:
    return f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={quote_plus(keyword.strip())}"
