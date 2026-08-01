"""FastAPI routes for the browser dashboard."""

from __future__ import annotations

from pathlib import Path
from decimal import Decimal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.import_pipeline import execute_import_dashboard_pipeline
from app.pipeline import (
    execute_dashboard_search,
    format_jpy,
    format_listing_price,
    format_percent,
)
from app.controlled_live_pipeline import execute_controlled_live_verification_search
from app.real_profit_pipeline import execute_real_profit_verification_search
from app.validation_pipeline import execute_profit_validation_search
from app.batch_profit_pipeline import execute_batch_profit_search, load_candidates_from_csv, load_candidates_from_listings
from app.schemas import (
    ConnectorExecutionView,
    ImportForm,
    ImportedListingRow,
    ProductDetailView,
    RankingCard,
    SavedOpportunityRow,
    SearchForm,
    ValidationForm,
    ValidationResultRow,
    RealProfitVerificationRow,
    ControlledLiveVerificationRow,
    BatchProfitRow,
    BatchHistoryRow,
)
from app.storage.batch_profit_repository import BatchProfitRepository
from app.storage.models import OpportunityStatus
from app.store import (
    BatchProfitResultStore,
    DashboardResultStore,
    SQLiteMarketListingStore,
    SQLiteOpportunityStore,
    ValidationResultStore,
)
from marketplace.importers.csv_importer import CSVImporter
from marketplace.importers.converters import market_listing_record_to_market_listing
from marketplace.importers.manual_importer import ManualImporter
from profit_discovery.discovery_validation.models import PRIORITY_CATEGORIES, TIER_S_BRANDS
from profit_discovery.discovery_validation.ranking import (
    validation_opportunity_to_arbitrage,
)
from profit_discovery.discovery_validation.real_profit_models import REAL_ROUTE_BRANDS
from profit_discovery.discovery_validation.real_profit_verification import real_profit_to_arbitrage
from profit_discovery.models import BuyDecision
from marketplace.acquisition_workspace.models import confidence_sort_key

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATUS_TRANSITIONS: dict[OpportunityStatus, tuple[OpportunityStatus, ...]] = {
    OpportunityStatus.NEW: (OpportunityStatus.WATCHING, OpportunityStatus.SKIPPED),
    OpportunityStatus.WATCHING: (OpportunityStatus.PURCHASED, OpportunityStatus.SKIPPED),
    OpportunityStatus.PURCHASED: (),
    OpportunityStatus.SKIPPED: (OpportunityStatus.WATCHING,),
}


def _get_snapshot_store(request: Request) -> DashboardResultStore:
    return request.app.state.result_store


def _get_opportunity_store(request: Request) -> SQLiteOpportunityStore:
    return request.app.state.opportunity_store


def _get_market_listing_store(request: Request) -> SQLiteMarketListingStore:
    return request.app.state.market_listing_store


def _get_validation_store(request: Request) -> ValidationResultStore:
    return request.app.state.validation_store


def _build_ranking_cards(store: DashboardResultStore) -> list[RankingCard]:
    snapshot = store.get()
    if snapshot is None:
        return []

    cards: list[RankingCard] = []
    for item in snapshot.arbitrage_ranking:
        listing = snapshot.listings_by_id.get(item.external_id)
        cards.append(
            RankingCard(
                rank=item.recommendation_rank or 0,
                product_id=item.external_id,
                product=item.product,
                brand=item.brand,
                category=item.category,
                purchase_source=item.purchase_source,
                purchase_url=item.purchase_url,
                purchase_price=format_jpy(item.purchase_price),
                selling_market=item.selling_market,
                selling_url=item.selling_url,
                selling_price=format_jpy(item.selling_price),
                estimated_profit=format_jpy(item.estimated_profit),
                profit_margin=format_percent(item.profit_margin),
                demand_score=item.demand_score,
                turnover_score=item.turnover_score,
                arbitrage_score=item.arbitrage_score,
                decision=item.decision,
                market_source=item.market_source,
                condition=item.condition,
                listing_url=item.listing_url,
                listing_source=listing.source_type if listing is not None else item.market_source,
                listing_price=format_listing_price(listing),
            )
        )
    return cards


def _build_connector_executions(store: DashboardResultStore) -> list[ConnectorExecutionView]:
    snapshot = store.get()
    if snapshot is None:
        return []
    return [
        ConnectorExecutionView(
            market_name=execution.market_name,
            requested_source=execution.requested_source,
            actual_source=execution.actual_source,
            fallback_used=execution.fallback_used,
        )
        for execution in snapshot.connector_executions.values()
    ]


def _build_product_detail(
    store: DashboardResultStore,
    opportunity_store: SQLiteOpportunityStore,
    product_id: str,
) -> ProductDetailView:
    arbitrage = store.get_arbitrage(product_id)
    if arbitrage is None:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    snapshot = store.get()
    candidate = store.get_candidate(product_id)
    profit_rank = store.get_profit_rank(product_id)
    roi = "N/A"
    if candidate is not None and candidate.profit_result is not None:
        roi = format_percent(candidate.profit_result.roi)

    saved_record = opportunity_store.find_by_purchase_url(arbitrage.purchase_url)
    saved_status = saved_record.status.value if saved_record is not None else None
    status_actions = (
        [status.value for status in STATUS_TRANSITIONS[saved_record.status]]
        if saved_record is not None
        else []
    )

    return ProductDetailView(
        product_id=product_id,
        product=arbitrage.product,
        brand=arbitrage.brand,
        category=arbitrage.category,
        purchase_source=arbitrage.purchase_source,
        purchase_url=arbitrage.purchase_url,
        purchase_price=format_jpy(arbitrage.purchase_price),
        selling_market=arbitrage.selling_market,
        selling_url=arbitrage.selling_url,
        selling_price=format_jpy(arbitrage.selling_price),
        price_difference=format_jpy(arbitrage.price_difference),
        estimated_profit=format_jpy(arbitrage.estimated_profit),
        profit_margin=format_percent(arbitrage.profit_margin),
        roi=roi,
        demand_score=arbitrage.demand_score,
        turnover_score=arbitrage.turnover_score,
        arbitrage_score=arbitrage.arbitrage_score,
        profit_rank=(
            profit_rank.score.recommendation_rank
            if profit_rank is not None
            else None
        ),
        decision=arbitrage.decision,
        market_mode=snapshot.market_mode if snapshot is not None else "FIXTURE",
        market_source=arbitrage.market_source,
        condition=arbitrage.condition,
        listing_url=arbitrage.listing_url,
        saved_record_id=saved_record.id if saved_record is not None else None,
        saved_status=saved_status,
        status_actions=status_actions,
    )


def _build_saved_rows(opportunity_store: SQLiteOpportunityStore) -> list[SavedOpportunityRow]:
    rows: list[SavedOpportunityRow] = []
    for item in opportunity_store.list_all():
        assert item.id is not None
        rows.append(
            SavedOpportunityRow(
                id=item.id,
                product=item.product_name,
                brand=item.brand,
                purchase_source=item.purchase_source,
                profit=format_jpy(item.estimated_profit),
                score=item.arbitrage_score,
                status=item.status.value,
                created_date=item.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        )
    return rows


def _build_imported_rows(market_listing_store: SQLiteMarketListingStore) -> list[ImportedListingRow]:
    rows: list[ImportedListingRow] = []
    for item in market_listing_store.list_all():
        assert item.id is not None
        price_display = (
            format_jpy(item.price) if item.currency.upper() == "JPY" else f"{item.price:,.0f} {item.currency}"
        )
        rows.append(
            ImportedListingRow(
                id=item.id,
                product=item.title,
                brand=item.brand,
                market_name=item.market_name,
                price=price_display,
                condition=item.condition,
                url=item.url,
            )
        )
    return rows


def _build_validation_rows(store: ValidationResultStore) -> list[ValidationResultRow]:
    snapshot = store.get()
    if snapshot is None:
        return []
    rows: list[ValidationResultRow] = []
    for item in snapshot.validation_ranking:
        rows.append(
            ValidationResultRow(
                rank=item.recommendation_rank or 0,
                product_id=item.external_id,
                product=item.product,
                purchase_source=item.purchase_source,
                purchase_price=format_jpy(item.purchase_price),
                domestic_market=item.domestic_market,
                domestic_price=format_jpy(item.domestic_price),
                estimated_profit=format_jpy(item.estimated_profit),
                profit_margin=format_percent(item.profit_margin),
                demand_score=item.demand_score,
                turnover_score=item.turnover_score,
                decision=item.decision,
                can_save=item.decision == BuyDecision.BUY.value,
            )
        )
    return rows


def _build_real_profit_rows(store: ValidationResultStore) -> list[RealProfitVerificationRow]:
    snapshot = store.get()
    if snapshot is None or not snapshot.real_profit_results:
        return []
    rows: list[RealProfitVerificationRow] = []
    for item in snapshot.real_profit_results:
        rows.append(
            RealProfitVerificationRow(
                rank=item.recommendation_rank or 0,
                product_id=item.external_id,
                product=item.product,
                purchase_source=item.purchase_source,
                purchase_url=item.purchase_url,
                purchase_price=f"{item.purchase_price:,} {item.purchase_currency}",
                purchase_currency=item.purchase_currency,
                purchase_price_jpy=format_jpy(item.purchase_price_jpy_estimate),
                exchange_rate=item.exchange_rate_display,
                estimated_shipping=item.cost_breakdown.estimated_shipping,
                estimated_import_cost=item.cost_breakdown.estimated_import_cost,
                domestic_source=item.domestic_source,
                domestic_sold_samples=item.domestic_sold_samples,
                domestic_average=format_jpy(item.domestic_average_jpy),
                domestic_median=format_jpy(item.domestic_median_jpy),
                domestic_url=item.domestic_url,
                estimated_profit=format_jpy(item.estimated_profit),
                profit_margin=format_percent(item.profit_margin),
                roi=format_percent(item.roi),
                demand_score=item.demand_score,
                turnover_score=item.turnover_score,
                decision=item.decision,
                requested_mode=item.requested_mode,
                actual_purchase_source=item.actual_purchase_source,
                actual_domestic_source=item.actual_domestic_source,
                purchase_fallback=item.purchase_fallback_used,
                domestic_fallback=item.domestic_fallback_used,
                data_status=item.data_status,
                retrieved_at=item.retrieved_at,
                verification_complete=item.verification_complete,
                can_save=item.decision == BuyDecision.BUY.value,
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
                comparable_median=format_jpy(item.comparable_median_jpy),
                legacy_median=format_jpy(item.legacy_median_jpy),
                comparable_data_warning=item.comparable_data_warning,
            )
        )
    return rows


def _build_controlled_live_rows(store: ValidationResultStore) -> list[ControlledLiveVerificationRow]:
    snapshot = store.get()
    if snapshot is None or not snapshot.controlled_live_results:
        return []
    rows: list[ControlledLiveVerificationRow] = []
    for item in snapshot.controlled_live_results:
        rows.append(
            ControlledLiveVerificationRow(
                rank=item.recommendation_rank or 0,
                product_id=item.external_id,
                product=item.product,
                fashionphile_url=item.fashionphile_url,
                purchase_price=f"{item.purchase_price:,} {item.purchase_currency}",
                purchase_currency=item.purchase_currency,
                purchase_price_jpy=format_jpy(item.purchase_price_jpy_estimate),
                exchange_rate=item.exchange_rate_display,
                yahoo_search_terms=item.yahoo_search_terms,
                yahoo_sold_samples=item.yahoo_sold_samples,
                yahoo_matched_samples=item.yahoo_matched_samples,
                matching_score=item.matching_score,
                matching_reliability=item.matching_reliability,
                median_selling_price=format_jpy(item.median_selling_price_jpy),
                average_selling_price=format_jpy(item.average_selling_price_jpy),
                cost_configuration_status=item.cost_configuration_status,
                estimated_shipping=item.estimated_shipping,
                estimated_import_cost=item.estimated_import_cost,
                estimated_profit=format_jpy(item.estimated_profit),
                profit_margin=format_percent(item.profit_margin),
                roi=format_percent(item.roi),
                demand_score=item.demand_score,
                turnover_score=item.turnover_score,
                decision=item.decision,
                acquisition_status=item.acquisition_status,
                data_status=item.data_status,
                verification_complete=item.verification_complete,
                retrieved_at=item.retrieved_at,
                blocking_reason=item.blocking_reason,
            )
        )
    return rows


def _validation_template_context(
    *,
    form: ValidationForm,
    store: ValidationResultStore,
    message: str = "",
    errors: list[str] | None = None,
) -> dict:
    snapshot = store.get()
    is_real = form.verification_mode.upper() == "REAL" or (
        snapshot is not None and snapshot.verification_mode.upper() == "REAL"
    )
    is_controlled_live = form.verification_mode.upper() == "CONTROLLED_LIVE" or (
        snapshot is not None and snapshot.verification_mode.upper() == "CONTROLLED_LIVE"
    )
    real_rows = _build_real_profit_rows(store) if is_real else []
    controlled_live_rows = _build_controlled_live_rows(store) if is_controlled_live else []
    standard_rows = _build_validation_rows(store) if not is_real and not is_controlled_live else []
    return {
        "title": "LuxuryBrandProfitFinder",
        "form": form,
        "tier_s_brands": list(TIER_S_BRANDS),
        "real_route_brands": list(REAL_ROUTE_BRANDS),
        "priority_categories": list(PRIORITY_CATEGORIES),
        "rows": standard_rows,
        "real_rows": real_rows,
        "controlled_live_rows": controlled_live_rows,
        "result_count": (
            len(controlled_live_rows)
            if is_controlled_live
            else len(real_rows)
            if is_real
            else len(standard_rows)
        ),
        "is_real_mode": is_real,
        "is_controlled_live_mode": is_controlled_live,
        "blocking_reason": snapshot.blocking_reason if snapshot is not None else "",
        "message": message,
        "errors": errors or [],
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, saved: str | None = None, imported: str | None = None) -> HTMLResponse:
    """Render the dashboard landing page with default search values."""
    form = SearchForm()
    cards = _build_ranking_cards(_get_snapshot_store(request))
    message = ""
    if saved:
        message = "候補を保存しました。"
    elif imported:
        message = "取込が完了しました。ランキングを更新しました。"
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "subtitle": "中古高級品 利益ダッシュボード",
            "form": form,
            "cards": cards,
            "result_count": len(cards),
            "saved_message": message,
            "connector_executions": _build_connector_executions(_get_snapshot_store(request)),
        },
    )


@router.post("/search", response_class=HTMLResponse)
async def search_dashboard(
    request: Request,
    brand: str = Form(default="Louis Vuitton"),
    category: str = Form(default="Wallet"),
    market_mode: str = Form(default="FIXTURE"),
) -> HTMLResponse:
    """Execute Used Luxury discovery and render ranking cards."""
    store = _get_snapshot_store(request)
    form = SearchForm(brand=brand, category=category, market_mode=market_mode)
    execute_dashboard_search(
        store,
        brand=form.brand,
        category=form.category,
        market_mode=form.market_mode,
    )
    cards = _build_ranking_cards(store)
    connector_executions = _build_connector_executions(store)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "subtitle": "中古高級品 利益ダッシュボード",
            "form": form,
            "cards": cards,
            "result_count": len(cards),
            "saved_message": "",
            "connector_executions": connector_executions,
        },
    )


@router.post("/opportunities/{product_id}/save")
async def save_opportunity(request: Request, product_id: str) -> RedirectResponse:
    """Save one ranked opportunity to SQLite."""
    store = _get_snapshot_store(request)
    opportunity_store = _get_opportunity_store(request)
    arbitrage = store.get_arbitrage(product_id)
    if arbitrage is None:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    opportunity_store.save_arbitrage(arbitrage)
    return RedirectResponse(url="/?saved=1", status_code=303)


@router.get("/saved", response_class=HTMLResponse)
async def saved_opportunities(request: Request) -> HTMLResponse:
    """Render saved opportunity list."""
    opportunity_store = _get_opportunity_store(request)
    return templates.TemplateResponse(
        request,
        "saved.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "rows": _build_saved_rows(opportunity_store),
        },
    )


@router.post("/saved/{record_id}/status")
async def update_saved_status(
    request: Request,
    record_id: int,
    status: str = Form(...),
    redirect_to: str = Form(default="/saved"),
) -> RedirectResponse:
    """Update workflow status for one saved opportunity."""
    opportunity_store = _get_opportunity_store(request)
    try:
        next_status = OpportunityStatus(status.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="無効なステータスです") from exc
    updated = opportunity_store.update_status(record_id, next_status)
    if updated is None:
        raise HTTPException(status_code=404, detail="保存済み候補が見つかりません")
    return RedirectResponse(url=redirect_to, status_code=303)


@router.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: str) -> HTMLResponse:
    """Render one product detail page."""
    store = _get_snapshot_store(request)
    opportunity_store = _get_opportunity_store(request)
    detail = _build_product_detail(store, opportunity_store, product_id)
    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "detail": detail,
        },
    )


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request, imported: str | None = None) -> HTMLResponse:
    """Render manual and CSV import form."""
    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "form": ImportForm(),
            "message": "取込が完了しました。" if imported else "",
            "errors": [],
        },
    )


@router.post("/import/manual", response_class=HTMLResponse)
async def import_manual_listing(
    request: Request,
    title: str = Form(...),
    brand: str = Form(...),
    category: str = Form(default="Wallet"),
    condition: str = Form(default="Used"),
    price: str = Form(...),
    currency: str = Form(default="JPY"),
    market_name: str = Form(default="Fashionphile"),
    url: str = Form(default=""),
) -> HTMLResponse:
    """Create one listing from manual form input and run import pipeline."""
    store = _get_snapshot_store(request)
    market_listing_store = _get_market_listing_store(request)
    form = ImportForm(
        title=title,
        brand=brand,
        category=category,
        condition=condition,
        price=price,
        currency=currency,
        market_name=market_name,
        url=url,
    )
    try:
        listing = ManualImporter().create_listing(
            title=form.title,
            brand=form.brand,
            category=form.category,
            condition=form.condition,
            price=form.price,
            currency=form.currency,
            market_name=form.market_name,
            url=form.url,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "import.html",
            {
                "title": "LuxuryBrandProfitFinder",
                "form": form,
                "message": "",
                "errors": [str(exc)],
            },
            status_code=400,
        )

    execute_import_dashboard_pipeline(
        store,
        [listing],
        listing_repository=market_listing_store.repository,
    )
    return RedirectResponse(url="/?imported=1#rankings", status_code=303)


@router.post("/import/csv", response_class=HTMLResponse)
async def import_csv_listings(
    request: Request,
    csv_file: UploadFile = File(...),
) -> HTMLResponse:
    """Import listings from one uploaded CSV file."""
    store = _get_snapshot_store(request)
    market_listing_store = _get_market_listing_store(request)
    temp_path = PROJECT_ROOT / "data" / "uploads"
    temp_path.mkdir(parents=True, exist_ok=True)
    destination = temp_path / csv_file.filename
    destination.write_bytes(await csv_file.read())

    importer = CSVImporter()
    importer.load_csv(destination)
    importer.validate_rows()
    result = importer.to_market_listings()
    if not result.listings:
        return templates.TemplateResponse(
            request,
            "import.html",
            {
                "title": "LuxuryBrandProfitFinder",
                "form": ImportForm(),
                "message": "",
                "errors": result.errors or ["CSVに有効な行がありません。"],
            },
            status_code=400,
        )

    execute_import_dashboard_pipeline(
        store,
        result.listings,
        listing_repository=market_listing_store.repository,
    )
    return RedirectResponse(url="/?imported=1#rankings", status_code=303)


@router.get("/imported", response_class=HTMLResponse)
async def imported_listings(request: Request) -> HTMLResponse:
    """Render persisted imported market listings."""
    market_listing_store = _get_market_listing_store(request)
    return templates.TemplateResponse(
        request,
        "imported.html",
        {
            "title": "LuxuryBrandProfitFinder",
            "rows": _build_imported_rows(market_listing_store),
        },
    )


@router.get("/validation", response_class=HTMLResponse)
async def validation_page(request: Request, saved: str | None = None) -> HTMLResponse:
    """Render profit validation search page."""
    store = _get_validation_store(request)
    return templates.TemplateResponse(
        request,
        "validation.html",
        _validation_template_context(
            form=ValidationForm(),
            store=store,
            message="BUY候補を保存しました。" if saved else "",
        ),
    )


@router.post("/validation", response_class=HTMLResponse)
async def run_validation(
    request: Request,
    brand: str = Form(default="Chanel"),
    category: str = Form(default="Wallet"),
    market_mode: str = Form(default="FIXTURE"),
    verification_mode: str = Form(default="STANDARD"),
    manual_purchase_url: str = Form(default=""),
    manual_purchase_title: str = Form(default=""),
    manual_purchase_price: str = Form(default=""),
    manual_purchase_currency: str = Form(default="USD"),
) -> HTMLResponse:
    """Execute profit validation discovery and render results."""
    store = _get_validation_store(request)
    form = ValidationForm(
        brand=brand,
        category=category,
        market_mode=market_mode,
        verification_mode=verification_mode,
        manual_purchase_url=manual_purchase_url,
        manual_purchase_title=manual_purchase_title,
        manual_purchase_price=manual_purchase_price,
        manual_purchase_currency=manual_purchase_currency,
    )
    try:
        if form.verification_mode.upper() == "REAL":
            execute_real_profit_verification_search(
                store,
                brand=form.brand,
                category=form.category,
                manual_purchase_url=form.manual_purchase_url,
                manual_purchase_title=form.manual_purchase_title,
                manual_purchase_price=form.manual_purchase_price,
                manual_purchase_currency=form.manual_purchase_currency,
            )
        else:
            execute_profit_validation_search(
                store,
                brand=form.brand,
                category=form.category,
                market_mode=form.market_mode,
            )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "validation.html",
            _validation_template_context(form=form, store=store, errors=[str(exc)]),
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "validation.html",
        _validation_template_context(form=form, store=store),
    )


@router.post("/validation/controlled-live", response_class=HTMLResponse)
async def run_controlled_live_validation(
    request: Request,
    brand: str = Form(default="Chanel"),
    category: str = Form(default="Wallet"),
) -> HTMLResponse:
    """Execute one controlled live browser acquisition check."""
    store = _get_validation_store(request)
    form = ValidationForm(
        brand=brand,
        category=category,
        market_mode="CONTROLLED_LIVE",
        verification_mode="CONTROLLED_LIVE",
    )
    try:
        execute_controlled_live_verification_search(
            store,
            brand=form.brand,
            category=form.category,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "validation.html",
            _validation_template_context(form=form, store=store, errors=[str(exc)]),
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "validation.html",
        _validation_template_context(form=form, store=store),
    )


@router.post("/validation/{product_id}/save")
async def save_validation_opportunity(request: Request, product_id: str) -> RedirectResponse:
    """Save one BUY validation opportunity to SQLite."""
    validation_store = _get_validation_store(request)
    opportunity_store = _get_opportunity_store(request)
    snapshot = validation_store.get()
    if snapshot is not None and snapshot.verification_mode.upper() == "REAL":
        real_item = next(
            (item for item in snapshot.real_profit_results if item.external_id == product_id),
            None,
        )
        if real_item is None:
            raise HTTPException(status_code=404, detail="検証結果が見つかりません")
        if real_item.decision != BuyDecision.BUY.value:
            raise HTTPException(status_code=400, detail="BUY候補のみ保存できます")
        opportunity_store.save_arbitrage(real_profit_to_arbitrage(real_item))
        return RedirectResponse(url="/validation?saved=1", status_code=303)

    item = validation_store.get_validation(product_id)
    if item is None:
        raise HTTPException(status_code=404, detail="検証結果が見つかりません")
    if item.decision != BuyDecision.BUY.value:
        raise HTTPException(status_code=400, detail="BUY候補のみ保存できます")
    opportunity_store.save_arbitrage(validation_opportunity_to_arbitrage(item))
    return RedirectResponse(url="/validation?saved=1", status_code=303)


def _get_batch_profit_store(request: Request) -> BatchProfitResultStore:
    store = getattr(request.app.state, "batch_profit_store", None)
    if store is None:
        store = BatchProfitResultStore()
        request.app.state.batch_profit_store = store
    return store


def _get_batch_profit_repository(request: Request) -> BatchProfitRepository:
    return BatchProfitRepository()


def _build_batch_rows(run) -> list[BatchProfitRow]:
    rows: list[BatchProfitRow] = []
    for item in run.results:
        warning = ", ".join(item.warnings) if item.warnings else item.comparable_warning
        rows.append(
            BatchProfitRow(
                rank=item.rank,
                candidate_id=item.candidate.candidate_id,
                product=item.candidate.title,
                purchase_source=item.candidate.purchase_source,
                purchase_price=f"{item.candidate.purchase_price:,} {item.candidate.currency}",
                purchase_price_jpy=format_jpy(item.candidate.purchase_price_jpy),
                subtype=item.candidate.detected_subtype,
                material=item.candidate.detected_material,
                accepted_comparables=item.accepted_comparable_count,
                reliability=item.domestic.reliability,
                recommended_estimate=format_jpy(item.domestic.recommended_selling_estimate_jpy),
                gross_profit=format_jpy(item.gross_estimated_profit),
                net_profit=format_jpy(item.net_estimated_profit) if item.net_estimated_profit is not None else "Not configured",
                margin=format_percent(item.profit_margin),
                roi=format_percent(item.roi),
                decision=item.batch_decision,
                data_status=item.data_status,
                warning=warning,
                yahoo_source=item.yahoo_data_source,
                details_json=item.diagnostics,
            )
        )
    return rows


def _build_batch_history_rows(repository: BatchProfitRepository) -> list[BatchHistoryRow]:
    rows: list[BatchHistoryRow] = []
    for summary in repository.list_runs(limit=20):
        rows.append(
            BatchHistoryRow(
                batch_id=summary.batch_id,
                run_date=summary.completed_at,
                product_count=summary.total_candidates,
                strong_candidate_count=summary.strong_candidate_count,
                top_net_profit="N/A",
                data_status="MIXED",
                cost_profile=summary.cost_profile,
            )
        )
    return rows


@router.get("/profit-batch", response_class=HTMLResponse)
async def profit_batch_page(request: Request, batch_id: str | None = None) -> HTMLResponse:
    """Render batch real profit discovery page."""
    store = _get_batch_profit_store(request)
    repository = _get_batch_profit_repository(request)
    run = repository.get_run(batch_id) if batch_id else store.get()
    context = {
        "request": request,
        "title": "一括利益計算",
        "run": run,
        "rows": _build_batch_rows(run) if run else [],
        "history_rows": _build_batch_history_rows(repository),
        "errors": [],
    }
    return templates.TemplateResponse(request, "profit_batch.html", context)


@router.post("/profit-batch/run", response_class=HTMLResponse)
async def run_profit_batch(
    request: Request,
    cost_profile: str = Form(default="standard"),
    candidate_limit: int = Form(default=10),
    use_cache: str = Form(default="on"),
    csv_file: UploadFile | None = File(default=None),
    use_imported: str = Form(default=""),
) -> HTMLResponse:
    """Execute one batch profit discovery run."""
    store = _get_batch_profit_store(request)
    repository = _get_batch_profit_repository(request)
    errors: list[str] = []
    candidates = []
    import_errors: list[str] = []
    limit = max(1, min(candidate_limit, 20))

    if csv_file is not None and csv_file.filename:
        temp_path = PROJECT_ROOT / "data" / "uploads" / csv_file.filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(await csv_file.read())
        imported = load_candidates_from_csv(temp_path, limit=limit)
        candidates.extend(imported.candidates)
        import_errors.extend(imported.errors)

    if use_imported:
        listing_store = _get_market_listing_store(request)
        records = listing_store.list_all()
        listings = [market_listing_record_to_market_listing(record) for record in records[:limit]]
        imported = load_candidates_from_listings(listings, limit=limit)
        candidates.extend(imported.candidates)
        import_errors.extend(imported.errors)

    if not candidates:
        errors.append("バッチ候補がありません。CSVをアップロードするか、取込済み商品を選択してください。")

    run = None
    if candidates:
        run = execute_batch_profit_search(
            store=store,
            repository=repository,
            candidates=candidates[:limit],
            cost_profile_name=cost_profile,
            use_cache=use_cache == "on",
            import_errors=tuple(import_errors),
        )

    context = {
        "request": request,
        "title": "一括利益計算",
        "run": run,
        "rows": _build_batch_rows(run) if run else [],
        "history_rows": _build_batch_history_rows(repository),
        "errors": errors + import_errors,
    }
    return templates.TemplateResponse(request, "profit_batch.html", context)


@router.post("/profit-batch/{batch_id}/delete")
async def delete_profit_batch(request: Request, batch_id: str) -> RedirectResponse:
    """Delete one saved batch run."""
    repository = _get_batch_profit_repository(request)
    repository.delete_run(batch_id)
    return RedirectResponse(url="/profit-batch", status_code=303)


def _is_non_operational_workspace_batch(batch) -> bool:
    """Return True for smoke/fake/demo batches that must not auto-open in ops UI."""
    name = str(getattr(batch, "name", "") or "").lower()
    batch_id = str(getattr(batch, "workspace_batch_id", "") or "").lower()
    if batch_id in {"demo-workspace"} or batch_id.startswith("demo-"):
        return True
    markers = ("smoke", "fake test", "fixture demo", "smoke_candidates")
    return any(token in name for token in markers)


def _select_operational_batch_id(history: list, *, explicit_demo: bool) -> str | None:
    """Pick newest non-fixture batch for the operational landing page."""
    if explicit_demo:
        return None
    for batch in history or []:
        if not _is_non_operational_workspace_batch(batch):
            return str(batch.workspace_batch_id)
    return None


def _get_acquisition_service(request: Request):
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

    database_path = request.app.state.market_listing_store.repository._database_path
    return AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=database_path))


def _get_workflow_store(request: Request):
    from marketplace.acquisition_workspace.workflow import CandidateWorkflowStore

    existing = getattr(request.app.state, "workflow_store", None)
    if existing is not None:
        return existing
    database_path = Path(request.app.state.market_listing_store.repository._database_path)
    storage_path = database_path.parent / "acquisition_workflow.json"
    store = CandidateWorkflowStore(storage_path=storage_path)
    request.app.state.workflow_store = store
    return store


def _workflow_template_context(candidate_ids: list[str], request: Request) -> dict:
    from marketplace.acquisition_workspace.workflow import (
        build_workflow_views,
        filter_choices,
        selectable_statuses,
    )

    store = _get_workflow_store(request)
    return {
        "workflow_by_id": build_workflow_views(candidate_ids, store),
        "status_choices": [{"code": item.code, "label": item.label} for item in selectable_statuses()],
        "workflow_filters": filter_choices(),
    }


def _build_acquisition_workspace_summary(batch, rows: list) -> dict:
    from marketplace.acquisition_workspace.analysis_version import (
        has_profit_check_result,
        is_profit_analysis_current,
        needs_profit_reanalysis,
    )

    accepted = sum(1 for item in rows if item.quality_grade != "REJECTED" and not item.duplicate_of)
    pending = sum(
        1
        for item in rows
        if item.quality_grade != "REJECTED" and not is_profit_analysis_current(item)
    )
    rejected = sum(1 for item in rows if item.quality_grade == "REJECTED")
    profit_checked = sum(1 for item in rows if is_profit_analysis_current(item))
    needs_reanalysis = sum(1 for item in rows if needs_profit_reanalysis(item))
    profits = [
        item.last_net_profit or item.last_gross_profit
        for item in rows
        if is_profit_analysis_current(item)
        and (item.last_net_profit or item.last_gross_profit) is not None
    ]
    average_profit = (
        format_jpy(sum(profits, Decimal("0")) / Decimal(len(profits)))
        if profits
        else "N/A"
    )
    average_confidence = _average_confidence_label(rows)
    runtimes = {item.discovery_metadata.runtime_mode for item in rows if item.discovery_metadata.runtime_mode}
    runtime = next(iter(runtimes)) if len(runtimes) == 1 else "MIXED" if runtimes else "IMPORT"
    last_updated = max(
        (item.last_profit_checked_at or item.imported_at or item.acquired_at for item in rows),
        default=batch.updated_at if batch is not None else "",
    )
    return {
        "candidates": len(rows),
        "accepted": accepted,
        "pending": pending,
        "rejected": rejected,
        "profit_checked": profit_checked,
        "needs_reanalysis": needs_reanalysis,
        "average_profit": average_profit,
        "average_confidence": average_confidence,
        "last_updated": last_updated or "-",
        "discovery_runtime": runtime,
        "acquisition_mode": batch.source_type if batch is not None else "",
        "has_stale_profit_checks": any(has_profit_check_result(item) and not is_profit_analysis_current(item) for item in rows),
    }


def _average_confidence_label(rows: list) -> str:
    if not rows:
        return "LOW"
    score = sum(confidence_sort_key(item.data_truth_summary.confidence_level) for item in rows) / len(rows)
    if score >= 2.5:
        return "HIGH"
    if score >= 1.5:
        return "MEDIUM"
    return "LOW"


@router.get("/acquisition-workspace", response_class=HTMLResponse)
async def acquisition_workspace_page(
    request: Request,
    batch_id: str | None = None,
    status: str | None = None,
    intake_error: str | None = None,
    intake_ok: str | None = None,
    marketplace: str | None = None,
    imported: str | None = None,
    rejected: str | None = None,
    keyword: str | None = None,
    demo: int = Query(default=0),
    profit_ok: str | None = None,
    profit_done: str | None = None,
    profit_capped: str | None = None,
    profit_selected: str | None = None,
    profit_error: str | None = None,
) -> HTMLResponse:
    from marketplace.acquisition_workspace.demo_workspace import DemoWorkspaceProvider
    from marketplace.acquisition_workspace.ranking import (
        is_valid_source_listing_url,
        order_candidates_for_display,
        ranking_by_candidate_id,
        source_listing_url_warning,
    )
    from marketplace.acquisition_workspace.ui_messaging import (
        humanize_intake_error,
        summarize_marketplace_runs,
    )
    from marketplace.acquisition_workspace.workflow import FILTER_ALL, STATUS_BY_CODE
    from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles

    # Strict opt-in only. Never treat missing/empty/truthy-ish values as demo.
    explicit_demo = demo == 1

    service = _get_acquisition_service(request)
    batch = None
    rows = []
    ranking_by_id: dict = {}
    grade_a = grade_b = grade_c = eligible_count = 0
    workspace_summary = None
    demo_mode = False
    history = service.list_batches()
    operational_history = [item for item in history if not _is_non_operational_workspace_batch(item)]
    # Operational default: open newest non-fixture batch (never smoke/fake CSV leftovers).
    if not batch_id and operational_history and not explicit_demo:
        batch_id = _select_operational_batch_id(operational_history, explicit_demo=explicit_demo)
    if batch_id and batch_id != "demo-workspace" and not explicit_demo:
        # Guard: refuse to render smoke/fake batches even if linked directly.
        try:
            maybe_batch, _ = service.get_batch(batch_id)
        except KeyError:
            maybe_batch = None
        if maybe_batch is not None and _is_non_operational_workspace_batch(maybe_batch):
            batch_id = _select_operational_batch_id(operational_history, explicit_demo=False)
    if batch_id and batch_id != "demo-workspace" and not explicit_demo:
        batch, rows = service.get_batch(batch_id)
        ranking_by_id = ranking_by_candidate_id(rows)
        rows = order_candidates_for_display(rows)
        grade_a = sum(1 for item in rows if item.quality_grade == "A")
        grade_b = sum(1 for item in rows if item.quality_grade == "B")
        grade_c = sum(1 for item in rows if item.quality_grade == "C")
        eligible_count = sum(1 for item in rows if item.eligible_for_profit_check and not item.duplicate_of)
        workspace_summary = _build_acquisition_workspace_summary(batch, rows)
    elif batch_id == "demo-workspace" and not explicit_demo:
        # Never silently serve the in-memory demo batch without ?demo=1.
        batch_id = None

    from marketplace.acquisition_workspace.price_display import (
        build_analysis_badges,
        build_price_cells,
        build_title_cells,
        resolve_selling_estimate_bundle_from_batch_runs,
    )

    if DemoWorkspaceProvider.should_use_demo(
        current_rows=rows,
        history=history,
        explicit_demo=explicit_demo,
    ):
        demo_snapshot = DemoWorkspaceProvider.build()
        batch = demo_snapshot.batch
        rows = demo_snapshot.rows
        ranking_by_id = demo_snapshot.ranking_by_id
        workspace_summary = demo_snapshot.workspace_summary
        grade_a = demo_snapshot.grade_a
        grade_b = demo_snapshot.grade_b
        grade_c = demo_snapshot.grade_c
        eligible_count = demo_snapshot.eligible_count
        demo_mode = True
        selling_estimate_by_id = demo_snapshot.selling_estimate_by_id
        selling_meta_by_id = {}
    else:
        database_path = request.app.state.market_listing_store.repository._database_path
        selling_estimate_by_id, selling_meta_by_id = resolve_selling_estimate_bundle_from_batch_runs(
            rows,
            database_path=database_path,
        )

    price_cells = build_price_cells(
        rows,
        selling_estimate_by_id=selling_estimate_by_id,
        selling_meta_by_id=selling_meta_by_id,
    )
    title_cells = build_title_cells(rows)
    analysis_badges = build_analysis_badges(
        rows,
        ranking_by_id,
        url_warning_fn=source_listing_url_warning,
    )
    from marketplace.acquisition_workspace.analysis_version import analysis_status_view

    analysis_status_by_id = {
        row.candidate_id: analysis_status_view(row).to_dict() for row in rows
    }
    workflow_context = _workflow_template_context([row.candidate_id for row in rows], request)
    active_filter = (status or FILTER_ALL).strip().lower()
    if active_filter != FILTER_ALL and active_filter not in STATUS_BY_CODE:
        active_filter = FILTER_ALL

    notices: list[str] = []
    if intake_ok and imported is not None:
        market_label = marketplace or "取得元"
        rejected_count = rejected or "0"
        keyword_label = f"（{keyword}）" if keyword else ""
        notices.append(
            f"Imported {imported} candidates / Rejected {rejected_count} candidates"
        )
        notices.append(
            f"{market_label}{keyword_label}: {imported}件を取り込みました"
            + (f"（除外 {rejected_count}件）" if rejected_count not in {"", "0"} else "")
            + "。利益分析を実行してください。"
        )
    if profit_ok:
        if profit_capped:
            notices.append(
                f"利益分析が完了しました（未分析 {profit_selected or '?'}件のうち"
                f"次の{profit_capped}件を分析）。残りは「利益分析」を再実行してください。"
            )
        else:
            notices.append("利益分析が完了しました。ランキングを確認してください。")
    if profit_done:
        notices.append(
            "対象候補の利益分析はすべて完了しています。"
            "未分析の候補はありません（再実行しても同じ候補は再計算しません）。"
        )

    errors: list[str] = []
    if intake_error:
        errors.append(humanize_intake_error(intake_error, marketplace=marketplace or ""))
    if profit_error:
        errors.append(profit_error)

    brand_options = sorted({(row.brand or "").strip() for row in rows if (row.brand or "").strip()})
    marketplace_runs = summarize_marketplace_runs(
        operational_history if not explicit_demo else history
    )

    fx_batch_snapshot = None
    if batch is not None:
        from marketplace.acquisition_workspace.fx_store import load_snapshot_for_batch

        fx_batch_snapshot = load_snapshot_for_batch(batch.workspace_batch_id)
        if fx_batch_snapshot is not None:
            fx_batch_snapshot = fx_batch_snapshot.to_dict()

    profile = CostProfileStore(profiles=default_cost_profiles(), storage_path=PROJECT_ROOT / "data" / "cost_profiles.json").get("custom")
    response = templates.TemplateResponse(
        request,
        "acquisition_workspace.html",
        {
            "request": request,
            "title": "仕入れ候補ワークスペース",
            "batch": batch,
            "rows": rows,
            "ranking_by_id": ranking_by_id,
            "is_valid_source_listing_url": is_valid_source_listing_url,
            "source_listing_url_warning": source_listing_url_warning,
            "grade_a": grade_a,
            "grade_b": grade_b,
            "grade_c": grade_c,
            "eligible_count": eligible_count,
            "workspace_summary": workspace_summary,
            "history": operational_history if not explicit_demo else history,
            "demo_mode": demo_mode,
            "price_cells": price_cells,
            "title_cells": title_cells,
            "analysis_badges": analysis_badges,
            "analysis_status_by_id": analysis_status_by_id,
            "active_workflow_filter": active_filter,
            "errors": errors,
            "notices": notices,
            "brand_options": brand_options,
            "marketplace_runs": marketplace_runs,
            "fx_batch_snapshot": fx_batch_snapshot,
            "cost_profile": {
                "profile_name": profile.profile_name,
                "net_complete": profile.is_net_complete(),
                "missing_fields": profile.configured_fields(),
            },
            **workflow_context,
        },
    )
    # Prevent browsers/proxies from keeping a stale demo HTML snapshot.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/acquisition-workspace/candidate/{candidate_id}", response_class=HTMLResponse)
async def acquisition_candidate_detail_page(
    request: Request,
    candidate_id: str,
    batch_id: str | None = None,
    demo: int = Query(default=0),
) -> HTMLResponse:
    from marketplace.acquisition_workspace.demo_workspace import DemoWorkspaceProvider
    from marketplace.acquisition_workspace.detail_display import (
        build_sourcing_detail,
        resolve_batch_result_for_candidate,
        resolve_selling_from_batch_result,
    )
    from marketplace.acquisition_workspace.ranking import ranking_by_candidate_id
    from marketplace.acquisition_workspace.workflow import selectable_statuses, workflow_view

    workflow_store = _get_workflow_store(request)
    workflow = workflow_view(workflow_store.get(candidate_id))
    status_choices = [{"code": item.code, "label": item.label} for item in selectable_statuses()]

    explicit_demo = demo == 1
    # Demo candidates require explicit ?demo=1 — never fall back from candidate_id alone.
    if explicit_demo and candidate_id.startswith("demo-"):
        found = DemoWorkspaceProvider.find_candidate(candidate_id)
        if found is None:
            return HTMLResponse("候補が見つかりません", status_code=404)
        detail = build_sourcing_detail(
            candidate=found["candidate"],
            rank=found["rank"],
            batch_id=found["batch"].workspace_batch_id,
            demo_mode=True,
            selling_estimate=found["selling_estimate"],
            demo_detail=found["detail"],
        )
        response = templates.TemplateResponse(
            request,
            "acquisition_candidate_detail.html",
            {
                "request": request,
                "title": "仕入れ候補詳細",
                "detail": detail,
                "workflow": workflow,
                "status_choices": status_choices,
            },
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    if candidate_id.startswith("demo-") and not explicit_demo:
        return HTMLResponse(
            "デモ候補は ?demo=1 が必要です。通常運用では実データのみ表示します。",
            status_code=404,
        )

    if not batch_id:
        return HTMLResponse("batch_id が必要です", status_code=400)

    service = _get_acquisition_service(request)
    try:
        batch, rows = service.get_batch(batch_id)
    except KeyError:
        return HTMLResponse("バッチが見つかりません", status_code=404)

    candidate = next((item for item in rows if item.candidate_id == candidate_id), None)
    if candidate is None:
        return HTMLResponse("候補が見つかりません", status_code=404)

    ranks = ranking_by_candidate_id(rows)
    database_path = request.app.state.market_listing_store.repository._database_path
    batch_result = resolve_batch_result_for_candidate(candidate, database_path=database_path)
    selling_estimate = resolve_selling_from_batch_result(batch_result)
    detail = build_sourcing_detail(
        candidate=candidate,
        rank=ranks.get(candidate_id),
        batch_id=batch.workspace_batch_id,
        demo_mode=False,
        selling_estimate=selling_estimate,
        batch_result=batch_result,
    )
    response = templates.TemplateResponse(
        request,
        "acquisition_candidate_detail.html",
        {
            "request": request,
            "title": "仕入れ候補詳細",
            "detail": detail,
            "workflow": workflow,
            "status_choices": status_choices,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@router.post("/acquisition-workspace/workflow/{candidate_id}")
async def update_candidate_workflow(request: Request, candidate_id: str) -> JSONResponse:
    """Update operator workflow status and/or notes without touching ranking/profit."""
    from marketplace.acquisition_workspace.workflow import workflow_view

    store = _get_workflow_store(request)
    content_type = (request.headers.get("content-type") or "").lower()
    status = None
    notes = None
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="無効なリクエストです")
        if "status" in payload:
            status = payload.get("status")
        if "notes" in payload:
            notes = payload.get("notes")
    else:
        form = await request.form()
        if "status" in form:
            status = form.get("status")
        if "notes" in form:
            notes = form.get("notes")

    if status is None and notes is None:
        raise HTTPException(status_code=400, detail="status または notes が必要です")

    try:
        updated = store.update(candidate_id, status=status, notes=notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse({"ok": True, "workflow": workflow_view(updated)})


@router.post("/acquisition-workspace/import/csv")
async def acquisition_import_csv(request: Request, csv_file: UploadFile = File(...)) -> RedirectResponse:
    service = _get_acquisition_service(request)
    temp = PROJECT_ROOT / "data" / "uploads" / csv_file.filename
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(await csv_file.read())
    batch = service.import_csv(temp)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={batch.workspace_batch_id}", status_code=303)


@router.post("/acquisition-workspace/import/manual")
async def acquisition_import_manual(request: Request) -> RedirectResponse:
    form = await request.form()
    rows = []
    for index in range(10):
        title = str(form.get(f"title_{index}", "")).strip()
        price = str(form.get(f"price_{index}", "")).strip()
        url = str(form.get(f"url_{index}", "")).strip()
        if not title and not price and not url:
            continue
        rows.append(
            {
                "title": title,
                "price": price,
                "currency": str(form.get(f"currency_{index}", "USD")).strip(),
                "url": url,
                "source": str(form.get(f"source_{index}", "Manual")).strip(),
            }
        )
    service = _get_acquisition_service(request)
    batch = service.import_manual_rows(rows)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={batch.workspace_batch_id}", status_code=303)


@router.post("/acquisition-workspace/import/html")
async def acquisition_import_html(request: Request, html_files: list[UploadFile] = File(default=[])) -> RedirectResponse:
    from marketplace.acquisition_workspace.ui_messaging import (
        humanize_intake_error,
        workspace_intake_error_url,
        workspace_intake_success_url,
    )

    service = _get_acquisition_service(request)
    files = []
    for upload in html_files:
        files.append((upload.filename or "saved.html", (await upload.read()).decode("utf-8", errors="replace")))
    try:
        batch = service.import_saved_html_files(files)
    except Exception as exc:
        return RedirectResponse(
            url=workspace_intake_error_url(humanize_intake_error(str(exc), marketplace="Saved HTML")),
            status_code=303,
        )
    if not batch.total_rows:
        return RedirectResponse(
            url=workspace_intake_error_url(
                humanize_intake_error("No products found in HTML", marketplace="Saved HTML")
            ),
            status_code=303,
        )
    return RedirectResponse(
        url=workspace_intake_success_url(
            batch_id=batch.workspace_batch_id,
            marketplace="Saved HTML",
            imported=int(batch.accepted_count or batch.total_rows or 0),
            rejected=int(batch.rejected_count or 0),
        ),
        status_code=303,
    )


@router.post("/acquisition-workspace/import/public-url")
async def acquisition_import_public_url(
    request: Request,
    url: str = Form(...),
    title: str = Form(...),
    price: str = Form(...),
    currency: str = Form(default="USD"),
) -> RedirectResponse:
    from decimal import Decimal

    service = _get_acquisition_service(request)
    batch = service.import_public_url(url=url, title=title, price=Decimal(price), currency=currency)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={batch.workspace_batch_id}", status_code=303)


def _redirect_live_intake(result, *, marketplace: str, keyword: str, service=None) -> RedirectResponse:
    from marketplace.acquisition_workspace.ui_messaging import (
        humanize_intake_error,
        workspace_intake_error_url,
        workspace_intake_success_url,
    )

    if not result.batch_id:
        message = humanize_intake_error(result.detail or "", marketplace=marketplace)
        return RedirectResponse(url=workspace_intake_error_url(message), status_code=303)
    imported = int(getattr(result, "listing_count", 0) or 0)
    rejected = 0
    if service is not None:
        try:
            batch, _ = service.get_batch(result.batch_id)
            rejected = int(getattr(batch, "rejected_count", 0) or 0)
        except Exception:
            rejected = 0
    return RedirectResponse(
        url=workspace_intake_success_url(
            batch_id=result.batch_id,
            marketplace=marketplace,
            imported=imported,
            rejected=rejected,
            keyword=keyword,
        ),
        status_code=303,
    )


@router.post("/acquisition-workspace/import/fashionphile-live")
async def acquisition_import_fashionphile_live(
    request: Request,
    keyword: str = Form(...),
    limit: int = Form(default=20),
    html_file: UploadFile | None = File(default=None),
) -> RedirectResponse:
    """Search Fashionphile live, or parse an uploaded saved search HTML page."""
    from marketplace.acquisition_workspace.live_fashionphile_intake import import_fashionphile_keyword

    service = _get_acquisition_service(request)
    html: str | None = None
    if html_file is not None and html_file.filename:
        raw = await html_file.read()
        html = raw.decode("utf-8", errors="ignore")
    result = import_fashionphile_keyword(
        service,
        keyword,
        limit=max(1, min(int(limit), 50)),
        html=html,
    )
    return _redirect_live_intake(result, marketplace="Fashionphile", keyword=keyword, service=service)


@router.options("/acquisition-workspace/import/browser-capture")
async def acquisition_browser_capture_options() -> JSONResponse:
    """CORS preflight for the Chrome extension capture endpoint."""
    return JSONResponse(content={"ok": True})


@router.options("/acquisition-workspace/import/browser-capture/known-urls")
async def acquisition_browser_capture_known_urls_options() -> JSONResponse:
    return JSONResponse(content={"ok": True})


@router.post("/acquisition-workspace/import/browser-capture/known-urls")
async def acquisition_browser_capture_known_urls(request: Request) -> JSONResponse:
    """Return which Fashionphile product URLs are already imported (backend source of truth)."""
    from marketplace.acquisition_workspace.browser_capture import resolve_known_urls

    if request.headers.get("X-BrandProfitFinder-Capture") != "1":
        return JSONResponse(
            status_code=403,
            content={"ok": False, "user_message": "BrandProfitFinderへ接続できません"},
        )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "有効な商品URLを取得できませんでした"},
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "有効な商品URLを取得できませんでした"},
        )
    service = _get_acquisition_service(request)
    result = resolve_known_urls(service, payload)
    status = 200 if result.ok else 400
    return JSONResponse(
        status_code=status,
        content={
            "ok": result.ok,
            "user_message": result.user_message,
            "known_urls": list(result.known_urls),
            "known_count": result.known_count,
            "queried_count": result.queried_count,
            "continuation_batch_id": result.continuation_batch_id,
            "errors": list(result.errors),
        },
    )


@router.post("/acquisition-workspace/import/browser-capture")
async def acquisition_import_browser_capture(request: Request) -> JSONResponse:
    """Accept Fashionphile products captured from the Chrome extension."""
    from marketplace.acquisition_workspace.browser_capture import (
        MAX_CAPTURE_PRODUCTS,
        import_browser_capture,
    )

    # Narrow development policy: require capture header; origin checked in middleware.
    if request.headers.get("X-BrandProfitFinder-Capture") != "1":
        return JSONResponse(
            status_code=403,
            content={"ok": False, "user_message": "BrandProfitFinderへ接続できません"},
        )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "有効な商品URLを取得できませんでした"},
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "有効な商品URLを取得できませんでした"},
        )
    # Hard size guard (approx JSON object breadth).
    products = payload.get("products")
    if isinstance(products, list) and len(products) > MAX_CAPTURE_PRODUCTS:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "user_message": f"一度に取り込める商品は{MAX_CAPTURE_PRODUCTS}件までです",
            },
        )

    service = _get_acquisition_service(request)
    # Extension always runs profit; tests may set run_profit=false to avoid live browsers.
    run_profit = bool(payload.get("run_profit", True))
    result = import_browser_capture(service, payload, run_profit=run_profit)
    status = 200 if result.ok else 400
    return JSONResponse(
        status_code=status,
        content={
            "ok": result.ok,
            "user_message": result.user_message,
            "batch_id": result.batch_id,
            "captured_count": result.captured_count,
            "detected_count": result.detected_count,
            "valid_count": result.valid_count,
            "duplicate_count": result.duplicate_count,
            "rejected_count": result.rejected_count,
            "imported_count": result.imported_count,
            "imported_this_run": result.imported_this_run,
            "already_imported_count": result.already_imported_count,
            "remaining_count": result.remaining_count,
            "skipped_already_imported": result.skipped_already_imported,
            "eligible_count": result.eligible_count,
            "analyzed_count": result.analyzed_count,
            "unanalyzed_count": result.unanalyzed_count,
            "ranked_count": result.ranked_count,
            "workspace_url": result.workspace_url,
            "rejection_reasons": result.rejection_reasons or {},
            "errors": list(result.errors),
            "submitted_urls": list(result.submitted_urls),
            "imported_urls": list(result.imported_urls),
            "duplicate_urls": list(result.duplicate_urls),
            "within_budget_count": result.within_budget_count,
            "over_budget_count": result.over_budget_count,
            "currency_unknown_count": result.currency_unknown_count,
            "fx_unavailable_count": result.fx_unavailable_count,
            "budget_excluded_count": result.budget_excluded_count,
            "budget_limit_jpy": result.budget_limit_jpy,
            "fx_snapshot_id": result.fx_snapshot_id,
            "fx_summary": result.fx_summary,
            "converted_prices": list(result.converted_prices),
        },
    )


@router.options("/acquisition-workspace/bulk-acquisition/start")
async def bulk_acquisition_start_options() -> JSONResponse:
    return JSONResponse(content={"ok": True})


@router.post("/acquisition-workspace/bulk-acquisition/start")
async def bulk_acquisition_start(request: Request) -> JSONResponse:
    """Create FX snapshot + validate budget before popular-brand bulk acquisition."""
    from marketplace.acquisition_workspace.budget_filter import (
        BUDGET_PRESET_LABELS,
        budget_label,
        parse_budget_limit_jpy,
    )
    from marketplace.acquisition_workspace.bulk_acquisition import start_bulk_session
    from marketplace.acquisition_workspace.fx_provider import acquire_session_fx_snapshot
    from marketplace.acquisition_workspace.popular_brands import load_popular_brands

    if request.headers.get("X-BrandProfitFinder-Capture") != "1":
        return JSONResponse(
            status_code=403,
            content={"ok": False, "user_message": "BrandProfitFinderへ接続できません"},
        )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "リクエストが不正です"},
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "リクエストが不正です"},
        )

    selected = payload.get("selected_brands") or []
    if not isinstance(selected, list) or not selected:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "user_message": "ブランドを選択してください"},
        )

    preset = str(payload.get("budget_preset") or "none")
    custom = payload.get("budget_custom_jpy")
    if preset in ("none", "制限なし"):
        budget_limit, budget_err = None, ""
    elif preset in ("custom", "自由入力"):
        budget_limit, budget_err = parse_budget_limit_jpy("custom", custom)
    else:
        budget_limit, budget_err = parse_budget_limit_jpy(preset, custom)
    if budget_err:
        return JSONResponse(status_code=400, content={"ok": False, "user_message": budget_err})

    # Provisional session id for FX binding; client may keep this session_id.
    catalog = load_popular_brands()
    try:
        session = start_bulk_session(
            catalog,
            [str(item) for item in selected],
            budget_limit_jpy=budget_limit,
            budget_preset=preset,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "user_message": str(exc)})

    fx = acquire_session_fx_snapshot(session.session_id)
    if not fx.ok or fx.snapshot is None:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "user_message": fx.user_message
                or "為替レートを取得できません。仕入れ上限付き一括取得を開始できません。",
                "can_retry": True,
                "failure_reason": fx.failure_reason,
            },
        )

    snap = fx.snapshot
    session.fx_snapshot_id = snap.snapshot_id
    session.fx_summary = snap.to_dict()
    session.budget_limit_jpy = budget_limit
    session.budget_preset = preset

    brand_labels = [
        session.brands[name].display_name
        for name in session.brand_order
        if name in session.brands
    ]
    summary_text = (
        f"選択ブランド:\n{('、'.join(brand_labels))}\n\n"
        f"仕入れ価格上限:\n{budget_label(budget_limit)}\n\n"
        f"使用予定為替:\n取得済み（{snap.source_name}）"
    )

    return JSONResponse(
        content={
            "ok": True,
            "user_message": fx.user_message,
            "session": session.to_dict(),
            "fx_snapshot": snap.to_dict(),
            "budget_limit_jpy": budget_limit,
            "budget_preset": preset,
            "budget_label": budget_label(budget_limit),
            "budget_preset_labels": BUDGET_PRESET_LABELS,
            "summary_text": summary_text,
            "rounding_rule": "Decimal * rate → ROUND_HALF_UP to whole JPY (profit_policy.money.round_jpy)",
        }
    )


@router.post("/acquisition-workspace/import/rebag-live")
async def acquisition_import_rebag_live(
    request: Request,
    keyword: str = Form(...),
    limit: int = Form(default=20),
    html_file: UploadFile | None = File(default=None),
) -> RedirectResponse:
    """Search Rebag live, or parse an uploaded saved search HTML page."""
    from marketplace.acquisition_workspace.live_rebag_intake import import_rebag_keyword

    service = _get_acquisition_service(request)
    html: str | None = None
    if html_file is not None and html_file.filename:
        raw = await html_file.read()
        html = raw.decode("utf-8", errors="ignore")
    result = import_rebag_keyword(
        service,
        keyword,
        limit=max(1, min(int(limit), 50)),
        html=html,
    )
    return _redirect_live_intake(result, marketplace="Rebag", keyword=keyword, service=service)


@router.post("/acquisition-workspace/import/realreal-live")
async def acquisition_import_realreal_live(
    request: Request,
    keyword: str = Form(...),
    limit: int = Form(default=20),
    html_file: UploadFile | None = File(default=None),
) -> RedirectResponse:
    """Search The RealReal live, or parse an uploaded saved search HTML page."""
    from marketplace.acquisition_workspace.live_realreal_intake import import_realreal_keyword

    service = _get_acquisition_service(request)
    html: str | None = None
    if html_file is not None and html_file.filename:
        raw = await html_file.read()
        html = raw.decode("utf-8", errors="ignore")
    result = import_realreal_keyword(
        service,
        keyword,
        limit=max(1, min(int(limit), 50)),
        html=html,
    )
    return _redirect_live_intake(result, marketplace="The RealReal", keyword=keyword, service=service)


@router.post("/acquisition-workspace/import/vestiaire-live")
async def acquisition_import_vestiaire_live(
    request: Request,
    keyword: str = Form(...),
    limit: int = Form(default=20),
    html_file: UploadFile | None = File(default=None),
) -> RedirectResponse:
    """Search Vestiaire Collective live, or parse an uploaded saved search HTML page."""
    from marketplace.acquisition_workspace.live_vestiaire_intake import import_vestiaire_keyword

    service = _get_acquisition_service(request)
    html: str | None = None
    if html_file is not None and html_file.filename:
        raw = await html_file.read()
        html = raw.decode("utf-8", errors="ignore")
    result = import_vestiaire_keyword(
        service,
        keyword,
        limit=max(1, min(int(limit), 50)),
        html=html,
    )
    return _redirect_live_intake(result, marketplace="Vestiaire Collective", keyword=keyword, service=service)


@router.post("/acquisition-workspace/import/existing")
async def acquisition_import_existing(request: Request) -> RedirectResponse:
    service = _get_acquisition_service(request)
    listing_store = _get_market_listing_store(request)
    listings = [market_listing_record_to_market_listing(record) for record in listing_store.list_all()]
    batch = service.import_existing_listings(listings)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={batch.workspace_batch_id}", status_code=303)


@router.post("/acquisition-workspace/{workspace_batch_id}/select-all-eligible")
async def acquisition_select_all(request: Request, workspace_batch_id: str) -> RedirectResponse:
    _get_acquisition_service(request).select_all_eligible(workspace_batch_id)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={workspace_batch_id}", status_code=303)


@router.post("/acquisition-workspace/{workspace_batch_id}/deselect-all")
async def acquisition_deselect_all(request: Request, workspace_batch_id: str) -> RedirectResponse:
    _get_acquisition_service(request).deselect_all(workspace_batch_id)
    return RedirectResponse(url=f"/acquisition-workspace?batch_id={workspace_batch_id}", status_code=303)


@router.post("/acquisition-workspace/{workspace_batch_id}/run-profit")
async def acquisition_run_profit(
    request: Request,
    workspace_batch_id: str,
    cost_profile: str = Form(default="standard"),
    use_cache: str = Form(default="on"),
) -> RedirectResponse:
    from marketplace.acquisition_workspace.continuous_analysis import get_continuous_analysis_controller
    from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES
    from urllib.parse import quote

    # Block manual single-tranche while continuous analysis is running for this workspace.
    controller = get_continuous_analysis_controller()
    service = _get_acquisition_service(request)
    progress = controller.get_progress(workspace_batch_id, service)
    if progress.currently_running or progress.status in {"running", "stopping"}:
        return RedirectResponse(
            url=(
                f"/acquisition-workspace?batch_id={workspace_batch_id}"
                f"&profit_error={quote('現在このワークスペースでは分析が実行中です。')}"
            ),
            status_code=303,
        )
    _, rows = service.get_batch(workspace_batch_id)

    from marketplace.acquisition_workspace.analysis_version import is_profit_analysis_current

    unanalyzed_before = sum(
        1
        for item in rows
        if item.eligible_for_profit_check
        and not item.duplicate_of
        and item.quality_grade != "REJECTED"
        and not is_profit_analysis_current(item)
    )
    try:
        run = service.run_batch_profit(
            workspace_batch_id,
            cost_profile_name=cost_profile,
            use_cache=use_cache == "on",
        )
    except ValueError as exc:
        # Safety net: never surface an unhandled 500 for batch-size / selection issues.
        return RedirectResponse(
            url=(
                f"/acquisition-workspace?batch_id={workspace_batch_id}"
                f"&profit_error={quote(str(exc))}"
            ),
            status_code=303,
        )
    if getattr(getattr(run, "summary", None), "status", "") == "already_complete":
        return RedirectResponse(
            url=f"/acquisition-workspace?batch_id={workspace_batch_id}&profit_done=1",
            status_code=303,
        )
    url = f"/acquisition-workspace?batch_id={workspace_batch_id}&profit_ok=1"
    if unanalyzed_before > MAX_BATCH_CANDIDATES:
        url += (
            f"&profit_capped={MAX_BATCH_CANDIDATES}"
            f"&profit_selected={unanalyzed_before}"
        )
    return RedirectResponse(url=url, status_code=303)


@router.post("/acquisition-workspace/{workspace_batch_id}/continuous-profit/start")
async def acquisition_continuous_profit_start(
    request: Request,
    workspace_batch_id: str,
) -> JSONResponse:
    from marketplace.acquisition_workspace.continuous_analysis import get_continuous_analysis_controller

    service = _get_acquisition_service(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        body = {}
    cost_profile = str(body.get("cost_profile") or "standard")
    use_cache = bool(body.get("use_cache", True))
    controller = get_continuous_analysis_controller()
    progress = controller.start(
        workspace_batch_id,
        service,
        cost_profile_name=cost_profile,
        use_cache=use_cache,
    )
    status_code = 200
    if progress.status == "busy":
        status_code = 409
    return JSONResponse(status_code=status_code, content=progress.to_dict())


@router.post("/acquisition-workspace/{workspace_batch_id}/continuous-profit/stop")
async def acquisition_continuous_profit_stop(
    request: Request,
    workspace_batch_id: str,
) -> JSONResponse:
    from marketplace.acquisition_workspace.continuous_analysis import get_continuous_analysis_controller

    service = _get_acquisition_service(request)
    controller = get_continuous_analysis_controller()
    progress = controller.stop(workspace_batch_id, service)
    return JSONResponse(content=progress.to_dict())


@router.get("/acquisition-workspace/{workspace_batch_id}/continuous-profit/status")
async def acquisition_continuous_profit_status(
    request: Request,
    workspace_batch_id: str,
) -> JSONResponse:
    from marketplace.acquisition_workspace.continuous_analysis import get_continuous_analysis_controller

    service = _get_acquisition_service(request)
    controller = get_continuous_analysis_controller()
    progress = controller.get_progress(workspace_batch_id, service)
    return JSONResponse(content=progress.to_dict())


@router.post("/acquisition-workspace/cost-profile/save")
async def acquisition_save_cost_profile(request: Request) -> RedirectResponse:
    from decimal import Decimal

    from profit_discovery.discovery_validation.batch_profit.costs import CostProfile, CostProfileStore, default_cost_profiles

    form = await request.form()
    store = CostProfileStore(profiles=default_cost_profiles(), storage_path=PROJECT_ROOT / "data" / "cost_profiles.json")
    profile = store.get("custom")

    def _decimal_field(name: str):
        raw = str(form.get(name, "")).strip()
        if not raw:
            return None
        value = Decimal(raw)
        if value < 0:
            raise HTTPException(status_code=400, detail=f"{name} は負の値にできません")
        return value

    def _rate_field(name: str):
        raw = str(form.get(name, "")).strip()
        if not raw:
            return None
        value = Decimal(raw)
        if value < 0 or value > 1:
            raise HTTPException(status_code=400, detail=f"{name} は 0 から 1 の範囲で指定してください")
        return value

    exchange_raw = str(form.get("exchange_rate", "")).strip()
    exchange_rate = float(exchange_raw) if exchange_raw else profile.exchange_rate
    updated = CostProfile(
        profile_name="Custom",
        exchange_rate=exchange_rate,
        international_shipping_jpy=_decimal_field("international_shipping_jpy"),
        forwarding_fee_jpy=_decimal_field("forwarding_fee_jpy"),
        import_duty_rate=_rate_field("import_duty_rate"),
        import_tax_rate=_rate_field("import_tax_rate"),
        payment_fee_rate=_rate_field("payment_fee_rate"),
        domestic_platform_fee_rate=_rate_field("domestic_platform_fee_rate"),
        domestic_shipping_jpy=_decimal_field("domestic_shipping_jpy"),
        inspection_or_repair_reserve_jpy=_decimal_field("inspection_or_repair_reserve_jpy"),
        miscellaneous_cost_jpy=_decimal_field("miscellaneous_cost_jpy"),
        assumption_note="User-edited custom profile",
    )
    store.save_profile(updated)
    return RedirectResponse(url="/acquisition-workspace", status_code=303)

