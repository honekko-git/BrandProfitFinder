"""Single-route real profit verification for Fashionphile -> Yahoo Auction."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.connectors.base import MarketConnectorUnavailableError
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.fixtures.fixture_connector import FixtureMarketConnector
from marketplace.connectors.live.fashionphile.connector import FashionphileLiveConnector
from marketplace.connectors.models import MarketListing
from marketplace.domestic_market.config import DomesticMarketRuntimeConfig
from marketplace.domestic_market.clients.resolver import DomesticMarketClientResolver
from marketplace.domestic_market.yahoo_auction.parser import parse_sold_items, to_market_price_data
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_validation.models import ValidationOpportunity
from profit_discovery.discovery_validation.ranking import validation_opportunity_to_arbitrage
from profit_discovery.discovery_validation.real_profit_config import (
    fashionphile_endpoint_status,
    resolve_usd_jpy_exchange_rate,
    yahoo_auction_endpoint_status,
)
from profit_discovery.discovery_validation.real_profit_models import (
    REAL_ROUTE_BRANDS,
    REAL_ROUTE_CATEGORY,
    CostBreakdownDisplay,
    DataStatus,
    DomesticSoldSummary,
    RealProfitVerificationResult,
)
from profit_discovery.discovery_validation.validator import ProfitValidationValidator
from profit_discovery.discovery_validation.yahoo_live_domestic import (
    apply_provisional_decision,
    format_accepted_comparables,
    format_diagnostics,
    format_rejected_samples,
    format_sample_titles,
    format_sold_prices,
    resolve_yahoo_live_domestic_summary,
)
from profit_discovery.discovery_validation.yahoo_sold_mapper import normalize_yahoo_sold_payload
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer
from marketplace.importers.converters import market_listing_to_supplier_product
from profit_intelligence.discovery_engine import DiscoveryEngine
from profit_intelligence.normalization import clamp_score
from supplier.models import to_product_candidate

NOT_CONFIGURED = "Not configured"


def is_real_route_brand(brand: str) -> bool:
    normalized = brand.strip().lower()
    return normalized in {item.lower() for item in REAL_ROUTE_BRANDS}


def is_real_route_category(category: str) -> bool:
    return category.strip().lower() == REAL_ROUTE_CATEGORY.lower()


def resolve_purchase_listings(
    *,
    brand: str,
    category: str,
    manual_listing: MarketListing | None = None,
    fashionphile_connector: FashionphileLiveConnector | None = None,
) -> tuple[list[MarketListing], str, str, bool]:
    """Resolve overseas purchase listings with honest source metadata."""
    query = f"{brand} {category}".strip()
    endpoint = fashionphile_endpoint_status()
    requested_mode = "LIVE" if endpoint.configured else "FIXTURE"

    if manual_listing is not None:
        return [manual_listing], requested_mode, DataStatus.IMPORT.value, False

    if endpoint.configured:
        connector = fashionphile_connector or FashionphileLiveConnector(
            config=MarketConnectorConfig.from_env(),
        )
        try:
            listings = connector.search_products(query)
            if listings:
                return listings, requested_mode, DataStatus.LIVE.value, False
        except (MarketConnectorUnavailableError, Exception):
            pass

    fixture = FixtureMarketConnector("Fashionphile")
    listings = [
        listing
        for listing in fixture.search_products(query)
        if brand.strip().lower() in listing.brand.lower()
    ]
    if not listings:
        listings = _load_brand_fixture_listings(brand, category)
    if not listings:
        listings = fixture.search_products(brand)
    actual_source = DataStatus.FIXTURE.value
    fallback_used = endpoint.configured
    return listings, requested_mode, actual_source, fallback_used


def resolve_domestic_sold_summary(
    *,
    keyword: str,
    yahoo_transport: object | None = None,
) -> DomesticSoldSummary:
    """Resolve Yahoo Auction sold summary with honest source metadata."""
    retrieved_at = datetime.now(tz=UTC).isoformat()
    endpoint = yahoo_auction_endpoint_status()
    requested_mode = "LIVE" if endpoint.configured else "FIXTURE"

    if yahoo_transport is not None:
        raw_items = yahoo_transport.search_sold_items(keyword)
        parsed = parse_sold_items(raw_items)
        summary = to_market_price_data(parsed, product_keyword=keyword)
        listing_url = parsed[0].url if parsed and parsed[0].url else _yahoo_search_url(keyword)
        return DomesticSoldSummary(
            market_name="Yahoo Auction",
            sample_count=int(summary["sample_count"]),
            average_price_jpy=Decimal(str(int(summary["average_price_jpy"]))),
            median_price_jpy=Decimal(str(int(summary["median_price_jpy"]))),
            listing_url=listing_url,
            actual_source=DataStatus.LIVE.value,
            fallback_used=False,
            retrieved_at=retrieved_at,
        )

    if endpoint.configured:
        resolution = DomesticMarketClientResolver(
            config=DomesticMarketRuntimeConfig.from_cli_live_market(),
        ).resolve_yahoo_auction()
        if resolution.client is not None:
            try:
                response = resolution.client.search_sold_prices(keyword)
                listing_url = _yahoo_search_url(keyword)
                return DomesticSoldSummary(
                    market_name="Yahoo Auction",
                    sample_count=response.sold_count,
                    average_price_jpy=Decimal(str(int(response.average_price))),
                    median_price_jpy=Decimal(str(int(response.average_price))),
                    listing_url=listing_url,
                    actual_source=DataStatus.LIVE.value,
                    fallback_used=resolution.execution.fallback_used if resolution.execution else False,
                    retrieved_at=response.retrieved_at,
                )
            except Exception:
                pass

    fixture_payload = _load_yahoo_fixture_payload(keyword)
    normalized = normalize_yahoo_sold_payload(fixture_payload)
    parsed = parse_sold_items(normalized)
    summary = to_market_price_data(parsed, product_keyword=keyword)
    listing_url = normalized[0]["url"] if normalized and normalized[0].get("url") else _yahoo_search_url(keyword)
    return DomesticSoldSummary(
        market_name="Yahoo Auction",
        sample_count=int(summary["sample_count"]),
        average_price_jpy=Decimal(str(int(summary["average_price_jpy"]))),
        median_price_jpy=Decimal(str(int(summary["median_price_jpy"]))),
        listing_url=str(listing_url),
        actual_source=DataStatus.FIXTURE.value,
        fallback_used=endpoint.configured,
        retrieved_at=retrieved_at,
    )


def build_real_profit_verifications(
    *,
    brand: str,
    category: str,
    manual_listing: MarketListing | None = None,
    fashionphile_connector: FashionphileLiveConnector | None = None,
    yahoo_transport: object | None = None,
    yahoo_html_by_query: dict[str, str] | None = None,
    yahoo_acquirer: YahooSoldAcquirer | None = None,
    exchange_rate: float | None = None,
) -> list[RealProfitVerificationResult]:
    """Build real profit verification rows for one brand/category route."""
    if not is_real_route_brand(brand):
        raise ValueError(f"Real profit route supports brands only: {', '.join(REAL_ROUTE_BRANDS)}")
    if not is_real_route_category(category):
        raise ValueError(f"Real profit route supports category only: {REAL_ROUTE_CATEGORY}")

    active_rate = exchange_rate if exchange_rate is not None else resolve_usd_jpy_exchange_rate()
    purchase_listings, requested_mode, purchase_actual, purchase_fallback = resolve_purchase_listings(
        brand=brand,
        category=category,
        manual_listing=manual_listing,
        fashionphile_connector=fashionphile_connector,
    )
    if not purchase_listings:
        return []

    use_yahoo_live = manual_listing is not None
    shared_domestic: DomesticSoldSummary | None = None

    if not use_yahoo_live:
        keyword = f"{brand} {category}".strip()
        shared_domestic = resolve_domestic_sold_summary(keyword=keyword, yahoo_transport=yahoo_transport)

    calculator = ProfitCalculator()
    discovery_engine = DiscoveryEngine()
    buy_engine = BuyDecisionEngine()
    validator = ProfitValidationValidator()

    results: list[RealProfitVerificationResult] = []
    for index, listing in enumerate(purchase_listings[:5], start=1):
        yahoo_search_queries = ""
        yahoo_live_sample_count = 0
        yahoo_matched_sample_count = 0
        yahoo_matched_sample_titles = ""
        yahoo_sold_prices_display = ""
        matching_score = 0.0
        matching_reliability = ""
        yahoo_diagnostics = ""
        purchase_subtype = ""
        purchase_material = ""
        yahoo_rejected_sample_count = 0
        yahoo_accepted_comparables = ""
        yahoo_rejected_samples = ""
        comparable_median_jpy = Decimal("0")
        legacy_median_jpy = Decimal("0")
        comparable_data_warning = ""

        if use_yahoo_live:
            live_resolution = resolve_yahoo_live_domestic_summary(
                listing=listing,
                brand=brand,
                category=category,
                html_by_query=yahoo_html_by_query,
                yahoo_acquirer=yahoo_acquirer,
            )
            domestic = live_resolution.domestic
            yahoo_search_queries = " | ".join(live_resolution.queries)
            yahoo_live_sample_count = live_resolution.live_sample_count
            yahoo_matched_sample_count = live_resolution.matched_count
            yahoo_matched_sample_titles = format_sample_titles(live_resolution.matched_samples)
            yahoo_sold_prices_display = format_sold_prices(live_resolution.matched_samples)
            matching_score = live_resolution.matching_score
            matching_reliability = live_resolution.reliability
            yahoo_diagnostics = format_diagnostics(list(live_resolution.diagnostics))
            purchase_subtype = live_resolution.purchase_subtype
            purchase_material = live_resolution.purchase_material
            yahoo_rejected_sample_count = live_resolution.rejected_count
            yahoo_accepted_comparables = format_accepted_comparables(live_resolution.comparable_diagnostics)
            yahoo_rejected_samples = format_rejected_samples(live_resolution.comparable_diagnostics)
            comparable_median_jpy = domestic.median_price_jpy
            legacy_median_jpy = live_resolution.legacy_median_jpy
            comparable_data_warning = live_resolution.comparable_data_warning
            selling_price = domestic.median_price_jpy
        else:
            domestic = shared_domestic
            selling_price = domestic.median_price_jpy if domestic is not None else Decimal("0")

        if domestic is None:
            continue

        supplier_product = market_listing_to_supplier_product(listing)
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
        profit_result = calculator.calculate(
            product,
            selling_price,
            domestic_market="yahoo_auction",
        )
        discovery_score = discovery_engine.score(profit_result)
        buy_decision = buy_engine.decide(profit_result, discovery_score)

        purchase_jpy = profit_result.purchase_price_jpy or Decimal("0")
        validation_base = ValidationOpportunity(
            product=listing.title,
            brand=listing.brand,
            category=listing.category,
            purchase_source=listing.market_name,
            purchase_price=purchase_jpy,
            purchase_url=listing.url,
            domestic_market=domestic.market_name,
            domestic_price=selling_price,
            domestic_url=domestic.listing_url,
            estimated_profit=profit_result.profit_jpy,
            profit_margin=profit_result.profit_margin,
            demand_score=clamp_score(yahoo_matched_sample_count * 12.0 if use_yahoo_live else domestic.sample_count * 12.0),
            turnover_score=clamp_score(yahoo_matched_sample_count * 10.0 if use_yahoo_live else domestic.sample_count * 10.0),
            validation_score=0.0,
            decision=buy_decision.decision.value,
            external_id=listing.id,
        )
        validated = validator.validate_one(validation_base)
        decision = validated.decision
        if use_yahoo_live:
            decision = apply_provisional_decision(
                validated.decision,
                reliability=matching_reliability or "LOW",
                matched_count=yahoo_matched_sample_count,
            )

        data_status = _resolve_data_status(
            purchase_actual=purchase_actual,
            domestic_actual=domestic.actual_source,
        )
        verification_complete = (
            data_status == DataStatus.LIVE.value
            and not purchase_fallback
            and not domestic.fallback_used
            and yahoo_matched_sample_count >= 3
        )

        results.append(
            RealProfitVerificationResult(
                product=listing.title,
                brand=listing.brand,
                category=listing.category,
                purchase_source=listing.market_name,
                purchase_url=listing.url,
                purchase_price=listing.price,
                purchase_currency=listing.currency,
                purchase_price_jpy_estimate=purchase_jpy,
                exchange_rate_display=(
                    f"{active_rate:g} JPY/USD"
                    if listing.currency.upper() != "JPY"
                    else "Not required (JPY)"
                ),
                cost_breakdown=_build_cost_breakdown(profit_result, selling_price, active_rate),
                domestic_source=domestic.market_name,
                domestic_sold_samples=yahoo_live_sample_count if use_yahoo_live else domestic.sample_count,
                domestic_average_jpy=domestic.average_price_jpy,
                domestic_median_jpy=domestic.median_price_jpy,
                domestic_url=domestic.listing_url,
                estimated_profit=profit_result.profit_jpy,
                profit_margin=profit_result.profit_margin,
                roi=profit_result.roi,
                demand_score=validated.demand_score,
                turnover_score=validated.turnover_score,
                validation_score=validated.validation_score,
                decision=decision,
                requested_mode=requested_mode,
                actual_purchase_source=purchase_actual,
                actual_domestic_source=domestic.actual_source,
                purchase_fallback_used=purchase_fallback,
                domestic_fallback_used=domestic.fallback_used,
                data_status=data_status,
                retrieved_at=listing.created_at.isoformat(),
                verification_complete=verification_complete,
                external_id=listing.id,
                recommendation_rank=index,
                yahoo_search_queries=yahoo_search_queries,
                yahoo_live_sample_count=yahoo_live_sample_count,
                yahoo_matched_sample_count=yahoo_matched_sample_count,
                yahoo_matched_sample_titles=yahoo_matched_sample_titles,
                yahoo_sold_prices_display=yahoo_sold_prices_display,
                matching_score=matching_score,
                matching_reliability=matching_reliability,
                yahoo_diagnostics=yahoo_diagnostics,
                purchase_subtype=purchase_subtype,
                purchase_material=purchase_material,
                yahoo_rejected_sample_count=yahoo_rejected_sample_count,
                yahoo_accepted_comparables=yahoo_accepted_comparables,
                yahoo_rejected_samples=yahoo_rejected_samples,
                comparable_median_jpy=comparable_median_jpy,
                legacy_median_jpy=legacy_median_jpy,
                comparable_data_warning=comparable_data_warning,
            )
        )
    ranked = sorted(results, key=lambda item: (-item.validation_score, -float(item.estimated_profit), item.external_id))
    return [_with_rank(item, rank) for rank, item in enumerate(ranked, start=1)]


def real_profit_to_validation_opportunity(item: RealProfitVerificationResult) -> ValidationOpportunity:
    """Convert one real profit row back to ValidationOpportunity."""
    return ValidationOpportunity(
        product=item.product,
        brand=item.brand,
        category=item.category,
        purchase_source=item.purchase_source,
        purchase_price=item.purchase_price_jpy_estimate,
        purchase_url=item.purchase_url,
        domestic_market=item.domestic_source,
        domestic_price=item.domestic_average_jpy,
        domestic_url=item.domestic_url,
        estimated_profit=item.estimated_profit,
        profit_margin=item.profit_margin,
        demand_score=item.demand_score,
        turnover_score=item.turnover_score,
        validation_score=item.validation_score,
        decision=item.decision,
        external_id=item.external_id,
        recommendation_rank=item.recommendation_rank,
    )


def real_profit_to_arbitrage(item: RealProfitVerificationResult):
    """Convert one real profit row to ArbitrageOpportunity for SQLite save."""
    return validation_opportunity_to_arbitrage(real_profit_to_validation_opportunity(item))


def _build_cost_breakdown(profit_result, domestic_price: Decimal, exchange_rate: float) -> CostBreakdownDisplay:
    shipping = profit_result.international_shipping_jpy
    import_cost = (
        profit_result.customs_duty_jpy
        + profit_result.import_tax_jpy
        + profit_result.other_costs_jpy
    )
    return CostBreakdownDisplay(
        purchase_price=_format_jpy_or_raw(profit_result.source_original_price, profit_result.source_currency),
        exchange_rate=f"{exchange_rate:g} JPY/USD" if profit_result.source_currency != "JPY" else "Not required (JPY)",
        estimated_shipping=_format_optional_jpy(shipping),
        estimated_import_cost=_format_optional_jpy(import_cost),
        domestic_selling_estimate=f"{int(domestic_price):,} JPY",
        estimated_profit=f"{int(profit_result.profit_jpy):,} JPY",
    )


def _format_optional_jpy(value: Decimal) -> str:
    if value is None or value <= 0:
        return NOT_CONFIGURED
    return f"{int(value):,} JPY"


def _format_jpy_or_raw(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return NOT_CONFIGURED
    if currency.upper() == "JPY":
        return f"{int(amount):,} JPY"
    return f"{amount} {currency.upper()}"


def _resolve_data_status(*, purchase_actual: str, domestic_actual: str) -> str:
    sources = {purchase_actual, domestic_actual}
    if len(sources) == 1:
        return next(iter(sources))
    if DataStatus.LIVE.value in sources and DataStatus.FIXTURE.value in sources:
        return DataStatus.MIXED.value
    if DataStatus.IMPORT.value in sources:
        return DataStatus.MIXED.value if len(sources) > 1 else DataStatus.IMPORT.value
    return DataStatus.MIXED.value


def _with_rank(item: RealProfitVerificationResult, rank: int) -> RealProfitVerificationResult:
    return RealProfitVerificationResult(
        product=item.product,
        brand=item.brand,
        category=item.category,
        purchase_source=item.purchase_source,
        purchase_url=item.purchase_url,
        purchase_price=item.purchase_price,
        purchase_currency=item.purchase_currency,
        purchase_price_jpy_estimate=item.purchase_price_jpy_estimate,
        exchange_rate_display=item.exchange_rate_display,
        cost_breakdown=item.cost_breakdown,
        domestic_source=item.domestic_source,
        domestic_sold_samples=item.domestic_sold_samples,
        domestic_average_jpy=item.domestic_average_jpy,
        domestic_median_jpy=item.domestic_median_jpy,
        domestic_url=item.domestic_url,
        estimated_profit=item.estimated_profit,
        profit_margin=item.profit_margin,
        roi=item.roi,
        demand_score=item.demand_score,
        turnover_score=item.turnover_score,
        validation_score=item.validation_score,
        decision=item.decision,
        requested_mode=item.requested_mode,
        actual_purchase_source=item.actual_purchase_source,
        actual_domestic_source=item.actual_domestic_source,
        purchase_fallback_used=item.purchase_fallback_used,
        domestic_fallback_used=item.domestic_fallback_used,
        data_status=item.data_status,
        retrieved_at=item.retrieved_at,
        verification_complete=item.verification_complete,
        external_id=item.external_id,
        recommendation_rank=rank,
        yahoo_search_queries=item.yahoo_search_queries,
        yahoo_live_sample_count=item.yahoo_live_sample_count,
        yahoo_matched_sample_count=item.yahoo_matched_sample_count,
        yahoo_matched_sample_titles=item.yahoo_matched_sample_titles,
        yahoo_sold_prices_display=item.yahoo_sold_prices_display,
        matching_score=item.matching_score,
        matching_reliability=item.matching_reliability,
        yahoo_diagnostics=item.yahoo_diagnostics,
        purchase_subtype=item.purchase_subtype,
        purchase_material=item.purchase_material,
        yahoo_rejected_sample_count=item.yahoo_rejected_sample_count,
        yahoo_accepted_comparables=item.yahoo_accepted_comparables,
        yahoo_rejected_samples=item.yahoo_rejected_samples,
        comparable_median_jpy=item.comparable_median_jpy,
        legacy_median_jpy=item.legacy_median_jpy,
        comparable_data_warning=item.comparable_data_warning,
    )


def _yahoo_search_url(keyword: str) -> str:
    query = keyword.strip().replace(" ", "+")
    return f"https://auctions.yahoo.co.jp/search/search?p={query}"


def _load_yahoo_fixture_payload(keyword: str) -> dict:
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[2]
    if "chanel" in keyword.lower():
        path = root / "tests" / "fixtures" / "yahoo_auction" / "chanel_wallet.json"
    else:
        path = root / "tests" / "fixtures" / "yahoo_auction" / "louis_vuitton_bag.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_brand_fixture_listings(brand: str, category: str) -> list[MarketListing]:
    from pathlib import Path
    import json

    from marketplace.connectors.live.fashionphile.parser import parse_fashionphile_response

    root = Path(__file__).resolve().parents[2]
    path = root / "tests" / "fixtures" / "fashionphile" / "fashionphile_products.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    listings = parse_fashionphile_response({"products": payload.get("products", [])})
    normalized_brand = brand.strip().lower()
    normalized_category = category.strip().lower()
    filtered = [
        listing
        for listing in listings
        if normalized_brand in listing.brand.lower()
        and (normalized_category in listing.category.lower() or normalized_category in listing.title.lower())
    ]
    return filtered
