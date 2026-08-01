"""Browser-extension capture intake for Fashionphile → acquisition workspace."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from marketplace.acquisition_workspace.fashionphile_dom_extract import (
    canonicalize_product_url,
    is_fashionphile_hostname,
    is_fashionphile_product_url,
)
from marketplace.acquisition_workspace.normalization import normalize_url
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus
from marketplace.browser_acquisition.fashionphile_acquirer import acquired_listing_to_market_listing


MAX_CAPTURE_PRODUCTS = 80
MAX_KNOWN_URL_LOOKUP = 300
EXTENSION_AUTO_PROFIT_CAP = 10
ALLOWED_MARKETPLACE = "Fashionphile"
EXTENSION_BATCH_PREFIX = "Fashionphile Extension:"
BULK_BATCH_PREFIX = "Fashionphile Bulk:"


@dataclass(frozen=True, slots=True)
class BrowserCaptureResult:
    ok: bool
    user_message: str
    batch_id: str = ""
    captured_count: int = 0
    valid_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    imported_count: int = 0
    eligible_count: int = 0
    analyzed_count: int = 0
    unanalyzed_count: int = 0
    ranked_count: int = 0
    workspace_url: str = ""
    rejection_reasons: dict[str, int] | None = None
    errors: tuple[str, ...] = ()
    detected_count: int = 0
    already_imported_count: int = 0
    imported_this_run: int = 0
    remaining_count: int = 0
    skipped_already_imported: int = 0
    submitted_urls: tuple[str, ...] = ()
    imported_urls: tuple[str, ...] = ()
    duplicate_urls: tuple[str, ...] = ()
    within_budget_count: int = 0
    over_budget_count: int = 0
    currency_unknown_count: int = 0
    fx_unavailable_count: int = 0
    budget_excluded_count: int = 0
    budget_limit_jpy: int | None = None
    fx_snapshot_id: str = ""
    fx_summary: dict[str, Any] | None = None
    converted_prices: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class KnownUrlsResult:
    ok: bool
    user_message: str
    known_urls: tuple[str, ...] = ()
    known_count: int = 0
    queried_count: int = 0
    continuation_batch_id: str = ""
    errors: tuple[str, ...] = ()


def collect_known_fashionphile_urls(service) -> set[str]:
    """Backend source of truth: canonical Fashionphile product URLs already imported."""
    known: set[str] = set()
    for batch in service.list_batches(limit=100):
        try:
            _, rows = service.get_batch(batch.workspace_batch_id)
        except Exception:  # noqa: BLE001
            continue
        for item in rows:
            url = (item.purchase_url or "").strip()
            if not url:
                continue
            source = (item.source_name or "").strip().lower()
            if source != "fashionphile" and "fashionphile.com" not in url.lower():
                continue
            try:
                known.add(canonicalize_product_url(url))
            except ValueError:
                key = normalize_url(url)
                if key:
                    known.add(key)
    return known


def find_continuation_batch_id(service, *, bulk_session_id: str = "") -> str:
    """Prefer an explicit bulk session batch, else newest Fashionphile Extension batch."""
    bulk_key = (bulk_session_id or "").strip()
    if bulk_key:
        target = f"{BULK_BATCH_PREFIX} {bulk_key}"
        for batch in service.list_batches(limit=50):
            if (batch.name or "") == target:
                return batch.workspace_batch_id
        return ""
    for batch in service.list_batches(limit=50):
        if (batch.name or "").startswith(EXTENSION_BATCH_PREFIX):
            return batch.workspace_batch_id
    return ""


def _canonical_url_list(raw_urls: Any, *, limit: int = MAX_KNOWN_URL_LOOKUP) -> list[str]:
    if not isinstance(raw_urls, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_urls[:limit]:
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            key = canonicalize_product_url(text)
        except ValueError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _remaining_for_page(visible_urls: list[str], known: set[str], detected_hint: int) -> int:
    if visible_urls:
        return sum(1 for url in visible_urls if url not in known)
    if detected_hint > 0:
        return max(0, detected_hint - len(known))
    return 0


def resolve_known_urls(service, payload: dict[str, Any]) -> KnownUrlsResult:
    marketplace = str(payload.get("source_marketplace") or "").strip()
    if marketplace and marketplace != ALLOWED_MARKETPLACE:
        return KnownUrlsResult(
            ok=False,
            user_message="このページは現在対応していません",
            errors=("unsupported marketplace",),
        )

    raw_urls = payload.get("urls")
    if raw_urls is None:
        raw_urls = []
    if not isinstance(raw_urls, list):
        return KnownUrlsResult(
            ok=False,
            user_message="有効な商品URLを取得できませんでした",
            errors=("urls must be a list",),
        )
    if len(raw_urls) > MAX_KNOWN_URL_LOOKUP:
        return KnownUrlsResult(
            ok=False,
            user_message=f"一度に照会できるURLは{MAX_KNOWN_URL_LOOKUP}件までです",
            errors=("too many urls",),
        )

    queried: list[str] = []
    for raw in raw_urls:
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            queried.append(canonicalize_product_url(text))
        except ValueError:
            continue

    known_all = collect_known_fashionphile_urls(service)
    if queried:
        matched = tuple(sorted(url for url in queried if url in known_all))
    else:
        matched = tuple(sorted(known_all))

    bulk_session_id = str(payload.get("bulk_session_id") or "").strip()
    return KnownUrlsResult(
        ok=True,
        user_message="",
        known_urls=matched,
        known_count=len(matched),
        queried_count=len(queried),
        continuation_batch_id=find_continuation_batch_id(
            service, bulk_session_id=bulk_session_id
        ),
    )


def import_browser_capture(
    service,
    payload: dict[str, Any],
    *,
    run_profit: bool = True,
    profit_cap: int = EXTENSION_AUTO_PROFIT_CAP,
    html_by_query: dict[str, str] | None = None,
    mercari_html_by_query: dict[str, str] | None = None,
    open_html_by_query: dict[str, str] | None = None,
) -> BrowserCaptureResult:
    """Validate extension payload, import Fashionphile listings, run capped profit."""
    from marketplace.acquisition_workspace.budget_filter import (
        evaluate_product_budget,
        format_budget_meta,
        parse_budget_limit_jpy,
    )
    from marketplace.acquisition_workspace.fx_models import FxSnapshot
    from marketplace.acquisition_workspace.fx_store import (
        link_batch_to_snapshot,
        load_snapshot,
        load_snapshot_for_session,
    )

    marketplace = str(payload.get("source_marketplace") or "").strip()
    source_page_url = str(payload.get("source_page_url") or "").strip()
    products = payload.get("products")
    detected_hint = int(payload.get("detected_count") or 0)
    bulk_session_id = str(payload.get("bulk_session_id") or "").strip()
    canonical_brand = str(payload.get("canonical_brand") or "").strip()
    fx_snapshot_id = str(payload.get("fx_snapshot_id") or "").strip()

    # Extension-supplied converted JPY is ignored; server recalculates.
    budget_limit: int | None = None
    raw_limit = payload.get("budget_limit_jpy", None)
    preset = payload.get("budget_preset", None)
    if bulk_session_id or preset is not None or raw_limit is not None:
        if preset in ("none", "制限なし") and (raw_limit is None or str(raw_limit).strip() == ""):
            budget_limit = None
        elif raw_limit is not None and str(raw_limit).strip() != "":
            budget_limit, budget_err = parse_budget_limit_jpy("custom", raw_limit)
            if budget_err:
                return BrowserCaptureResult(ok=False, user_message=budget_err, errors=(budget_err,))
        elif preset is not None:
            budget_limit, budget_err = parse_budget_limit_jpy(str(preset), raw_limit)
            if budget_err:
                return BrowserCaptureResult(ok=False, user_message=budget_err, errors=(budget_err,))

    snapshot: FxSnapshot | None = None
    if fx_snapshot_id:
        snapshot = load_snapshot(fx_snapshot_id)
    if snapshot is None and bulk_session_id:
        snapshot = load_snapshot_for_session(bulk_session_id)
    if snapshot is not None:
        fx_snapshot_id = snapshot.snapshot_id

    # Budget-filtered bulk requires a frozen snapshot.
    if bulk_session_id and budget_limit is not None and snapshot is None:
        return BrowserCaptureResult(
            ok=False,
            user_message="為替レートを取得できないため、仕入れ上限を判定できません。",
            errors=("fx_snapshot_required",),
            budget_limit_jpy=budget_limit,
        )

    if marketplace != ALLOWED_MARKETPLACE:
        return BrowserCaptureResult(
            ok=False,
            user_message="このページは現在対応していません",
            errors=("unsupported marketplace",),
        )
    if not isinstance(products, list):
        return BrowserCaptureResult(
            ok=False,
            user_message="有効な商品URLを取得できませんでした",
            errors=("products must be a list",),
        )
    if len(products) > MAX_CAPTURE_PRODUCTS:
        return BrowserCaptureResult(
            ok=False,
            user_message=f"一度に取り込める商品は{MAX_CAPTURE_PRODUCTS}件までです",
            errors=("too many products",),
        )

    if source_page_url:
        try:
            from urllib.parse import urlparse

            host = urlparse(source_page_url).hostname or ""
            if not is_fashionphile_hostname(host):
                return BrowserCaptureResult(
                    ok=False,
                    user_message="Fashionphileの検索結果ページを開いてください",
                    errors=("invalid source_page_url host",),
                )
        except Exception:  # noqa: BLE001
            return BrowserCaptureResult(
                ok=False,
                user_message="Fashionphileの検索結果ページを開いてください",
                errors=("invalid source_page_url",),
            )

    listings, rejected, reasons = _validate_products(
        products,
        canonical_brand=canonical_brand,
        bulk_session_id=bulk_session_id,
        source_page_url=source_page_url,
        fx_snapshot_id=fx_snapshot_id,
    )
    captured_count = len(products)
    duplicate_count = reasons.get("duplicate", 0)
    run_profit_flag = bool(payload.get("run_profit", run_profit))
    detected_count = max(detected_hint, captured_count)

    within_budget = 0
    over_budget = 0
    currency_unknown = reasons.get("ambiguous_currency", 0) + reasons.get("missing_or_invalid_price", 0)
    fx_unavailable = 0
    budget_excluded_urls: set[str] = set()
    converted_audit: list[dict[str, Any]] = []
    budget_pass_listings: list[AcquiredListing] = []

    if snapshot is not None and (budget_limit is not None or bulk_session_id):
        filtered: list[AcquiredListing] = []
        for item in listings:
            decision = evaluate_product_budget(
                price=item.price,
                currency=item.currency,
                snapshot=snapshot,
                budget_limit_jpy=budget_limit,
            )
            meta = format_budget_meta(decision, snapshot_id=snapshot.snapshot_id)
            item = replace(
                item,
                raw_title=(item.raw_title + "\n" if item.raw_title else "") + meta,
            )
            audit = {
                "url": item.url,
                "original_price": str(decision.original_price) if decision.original_price is not None else "",
                "original_currency": decision.original_currency,
                "fx_rate_used": str(decision.fx_rate_used) if decision.fx_rate_used is not None else "",
                "converted_purchase_price_jpy": (
                    str(decision.converted_purchase_price_jpy)
                    if decision.converted_purchase_price_jpy is not None
                    else ""
                ),
                "budget_filter_result": decision.result,
                "budget_filter_reason": decision.reason,
            }
            converted_audit.append(audit)
            if decision.result == "pass":
                within_budget += 1
                filtered.append(item)
                budget_pass_listings.append(item)
            elif decision.result == "over_budget":
                over_budget += 1
                budget_excluded_urls.add(item.url)
            elif decision.result == "currency_unavailable":
                fx_unavailable += 1
                budget_excluded_urls.add(item.url)
            elif decision.result in {"currency_missing", "unsupported_currency"}:
                currency_unknown += 1
                budget_excluded_urls.add(item.url)
            else:
                budget_excluded_urls.add(item.url)
        listings = filtered
    else:
        within_budget = len(listings)
        budget_pass_listings = list(listings)

    known = collect_known_fashionphile_urls(service)
    known_before = set(known)
    visible_urls = _canonical_url_list(payload.get("visible_urls"))
    fresh_listings: list[AcquiredListing] = []
    skipped_urls: list[str] = []
    submitted_urls = [item.url for item in budget_pass_listings]
    for item in listings:
        if item.url in known:
            skipped_urls.append(item.url)
            continue
        fresh_listings.append(item)
        known.add(item.url)

    already_imported_count = len(skipped_urls)
    page_already_before = (
        sum(1 for url in visible_urls if url in known_before)
        if visible_urls
        else already_imported_count
    )
    # Treat budget exclusions as handled for remaining (not system errors).
    handled_for_remaining = set(known_before) | budget_excluded_urls

    fx_summary = snapshot.to_dict() if snapshot is not None else None

    if not budget_pass_listings and not fresh_listings:
        # All excluded by budget / validation — not necessarily an error.
        if over_budget or fx_unavailable or currency_unknown:
            remaining_after = _remaining_for_page(
                visible_urls, handled_for_remaining | known_before, detected_count
            )
            return BrowserCaptureResult(
                ok=True,
                user_message=(
                    f"価格上限内の商品はありませんでした。"
                    f"（上限超過{over_budget}件 / 通貨・為替除外{fx_unavailable + currency_unknown}件）"
                    "\n※判定基準: 商品本体の円換算価格"
                ),
                batch_id=str(payload.get("workspace_batch_id") or "").strip()
                or find_continuation_batch_id(service, bulk_session_id=bulk_session_id),
                captured_count=captured_count,
                detected_count=detected_count,
                valid_count=0,
                duplicate_count=duplicate_count,
                rejected_count=sum(reasons.values()),
                imported_count=0,
                imported_this_run=0,
                already_imported_count=page_already_before or already_imported_count,
                remaining_count=remaining_after,
                within_budget_count=within_budget,
                over_budget_count=over_budget,
                currency_unknown_count=currency_unknown,
                fx_unavailable_count=fx_unavailable,
                budget_excluded_count=over_budget + fx_unavailable + currency_unknown,
                budget_limit_jpy=budget_limit,
                fx_snapshot_id=fx_snapshot_id,
                fx_summary=fx_summary,
                converted_prices=tuple(converted_audit),
                rejection_reasons=reasons,
            )
        return BrowserCaptureResult(
            ok=False,
            user_message="価格を取得できない商品を除外しました"
            if reasons.get("missing_or_invalid_price") or reasons.get("ambiguous_currency")
            else "有効な商品URLを取得できませんでした",
            captured_count=captured_count,
            detected_count=detected_count,
            valid_count=0,
            duplicate_count=duplicate_count,
            rejected_count=sum(reasons.values()),
            already_imported_count=already_imported_count,
            within_budget_count=within_budget,
            over_budget_count=over_budget,
            currency_unknown_count=currency_unknown,
            fx_unavailable_count=fx_unavailable,
            budget_limit_jpy=budget_limit,
            fx_snapshot_id=fx_snapshot_id,
            fx_summary=fx_summary,
            rejection_reasons=reasons,
            errors=tuple(rejected[:8]),
        )

    if not fresh_listings:
        continuation_id = (
            str(payload.get("workspace_batch_id") or "").strip()
            or find_continuation_batch_id(service, bulk_session_id=bulk_session_id)
        )
        remaining_after = _remaining_for_page(
            visible_urls, handled_for_remaining | known_before, detected_count
        )
        return BrowserCaptureResult(
            ok=True,
            user_message="このページの表示商品はすべて取り込み済みです。",
            batch_id=continuation_id,
            captured_count=captured_count,
            detected_count=detected_count,
            valid_count=len(budget_pass_listings),
            duplicate_count=duplicate_count + already_imported_count,
            rejected_count=sum(reasons.values()),
            imported_count=0,
            imported_this_run=0,
            already_imported_count=page_already_before or already_imported_count or detected_count,
            remaining_count=remaining_after,
            skipped_already_imported=already_imported_count,
            submitted_urls=tuple(submitted_urls),
            duplicate_urls=tuple(skipped_urls),
            within_budget_count=within_budget,
            over_budget_count=over_budget,
            currency_unknown_count=currency_unknown,
            fx_unavailable_count=fx_unavailable,
            budget_excluded_count=over_budget + fx_unavailable,
            budget_limit_jpy=budget_limit,
            fx_snapshot_id=fx_snapshot_id,
            fx_summary=fx_summary,
            converted_prices=tuple(converted_audit),
            workspace_url=(
                f"/acquisition-workspace?batch_id={continuation_id}"
                if continuation_id
                else "/acquisition-workspace"
            ),
            rejection_reasons=reasons,
        )

    market_listings = [acquired_listing_to_market_listing(item) for item in fresh_listings]
    continuation_id = (
        str(payload.get("workspace_batch_id") or "").strip()
        or find_continuation_batch_id(service, bulk_session_id=bulk_session_id)
    )
    appended = False
    if continuation_id:
        try:
            service.get_batch(continuation_id)
            batch = service.append_existing_listings(
                continuation_id,
                market_listings,
                fx_snapshot_id=fx_snapshot_id or None,
            )
            appended = True
        except Exception:  # noqa: BLE001
            continuation_id = ""
            appended = False
    if not appended:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        if bulk_session_id:
            batch_name = f"{BULK_BATCH_PREFIX} {bulk_session_id}"
        else:
            batch_name = f"{EXTENSION_BATCH_PREFIX} {stamp}"
        batch = service.import_existing_listings(
            market_listings,
            name=batch_name,
            fx_snapshot_id=fx_snapshot_id or None,
        )

    batch_id = batch.workspace_batch_id
    if fx_snapshot_id:
        link_batch_to_snapshot(batch_id, fx_snapshot_id)
    _, rows = service.get_batch(batch_id)
    eligible = [item for item in rows if item.eligible_for_profit_check and not item.duplicate_of]
    analyzed = 0
    ranked = 0
    # Auto-profit only on brand-new batches (first capture), not every continuation append.
    if run_profit_flag and eligible and not appended:
        service.select_all_eligible(batch_id)
        _, selected_rows = service.get_batch(batch_id)
        selected = [item for item in selected_rows if item.selected_for_profit_check]
        for item in selected[max(1, int(profit_cap)) :]:
            service.select_candidate(batch_id, item.candidate_id, selected=False)
        run = service.run_batch_profit(
            batch_id,
            use_cache=True,
            html_by_query=html_by_query,
            mercari_html_by_query=mercari_html_by_query,
            open_html_by_query=open_html_by_query,
        )
        analyzed = len([item for item in (run.results if run else [])])
        ranked = len([item for item in (run.results if run else []) if getattr(item, "rank", 0)])
        _, rows = service.get_batch(batch_id)

    imported_this_run = len(fresh_listings)
    known_after = collect_known_fashionphile_urls(service)
    handled_after = known_after | budget_excluded_urls
    if visible_urls:
        remaining_after = _remaining_for_page(visible_urls, handled_after, detected_hint)
    elif detected_hint > 0:
        remaining_after = max(0, detected_hint - page_already_before - imported_this_run - over_budget - fx_unavailable)
    else:
        remaining_after = 0

    if remaining_after > 0:
        user_message = (
            f"{detected_count}件の商品を検出しました。\n"
            f"{imported_this_run}件を取り込みました。\n"
            f"残り{remaining_after}件です。"
        )
    elif page_already_before and imported_this_run:
        user_message = (
            f"{detected_count}件の商品を検出しました。\n"
            f"追加で{imported_this_run}件を取り込みました。\n"
            f"すべて取り込み済みです。"
        )
    elif analyzed and max(0, len(eligible) - analyzed):
        user_message = (
            f"{len(rows)}件を取込、最初の{analyzed}件を利益分析"
            f"（残り{max(0, len(eligible) - analyzed)}件はワークスペースから追加分析できます）"
        )
    elif analyzed:
        user_message = f"{len(rows)}件を取込、利益分析を開始しました"
    else:
        user_message = f"{imported_this_run}件を取り込みました"

    if budget_limit is not None:
        user_message += (
            f"\n価格上限内:{within_budget} / 上限超過:{over_budget}"
            f"（商品本体の円換算価格で判定）"
        )

    unanalyzed = max(0, len(eligible) - analyzed)
    return BrowserCaptureResult(
        ok=True,
        user_message=user_message,
        batch_id=batch_id,
        captured_count=captured_count,
        detected_count=detected_count,
        valid_count=len(budget_pass_listings),
        duplicate_count=duplicate_count + already_imported_count,
        rejected_count=sum(reasons.values()),
        imported_count=imported_this_run,
        imported_this_run=imported_this_run,
        already_imported_count=page_already_before or already_imported_count,
        remaining_count=remaining_after,
        skipped_already_imported=already_imported_count,
        eligible_count=len(eligible),
        analyzed_count=analyzed,
        unanalyzed_count=unanalyzed,
        ranked_count=ranked,
        submitted_urls=tuple(submitted_urls),
        imported_urls=tuple(item.url for item in fresh_listings),
        duplicate_urls=tuple(skipped_urls),
        within_budget_count=within_budget,
        over_budget_count=over_budget,
        currency_unknown_count=currency_unknown,
        fx_unavailable_count=fx_unavailable,
        budget_excluded_count=over_budget + fx_unavailable + currency_unknown,
        budget_limit_jpy=budget_limit,
        fx_snapshot_id=fx_snapshot_id,
        fx_summary=fx_summary,
        converted_prices=tuple(converted_audit),
        workspace_url=(
            f"/acquisition-workspace?batch_id={batch_id}&profit_ok=1"
            if analyzed
            else f"/acquisition-workspace?batch_id={batch_id}"
        ),
        rejection_reasons=reasons,
    )


def _validate_products(
    products: list[Any],
    *,
    canonical_brand: str = "",
    bulk_session_id: str = "",
    source_page_url: str = "",
    fx_snapshot_id: str = "",
) -> tuple[list[AcquiredListing], list[str], dict[str, int]]:
    now = datetime.now(tz=UTC).isoformat()
    listings: list[AcquiredListing] = []
    rejected: list[str] = []
    reasons: dict[str, int] = {}
    seen: set[str] = set()
    meta_bits = []
    if bulk_session_id:
        meta_bits.append(f"bulk_session_id={bulk_session_id}")
    if source_page_url:
        meta_bits.append(f"source_page_url={source_page_url}")
    if fx_snapshot_id:
        meta_bits.append(f"fx_snapshot_id={fx_snapshot_id}")
    meta_prefix = ("; ".join(meta_bits) + "\n") if meta_bits else ""

    for index, raw in enumerate(products):
        if not isinstance(raw, dict):
            _bump(reasons, "malformed")
            rejected.append(f"item {index}: malformed")
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            _bump(reasons, "missing_title")
            rejected.append(f"item {index}: missing title")
            continue
        url_raw = str(raw.get("url") or "").strip()
        if not url_raw:
            _bump(reasons, "missing_url")
            rejected.append(f"item {index}: missing url")
            continue
        try:
            url = canonicalize_product_url(url_raw)
        except ValueError:
            _bump(reasons, "invalid_url")
            rejected.append(f"item {index}: invalid url")
            continue
        if not is_fashionphile_product_url(url):
            _bump(reasons, "invalid_url")
            rejected.append(f"item {index}: invalid url")
            continue
        availability = str(raw.get("availability") or "available").strip().lower()
        if availability in {"sold", "sold_out", "unavailable"}:
            _bump(reasons, "sold_or_unavailable")
            rejected.append(f"item {index}: sold/unavailable")
            continue
        # Prefer current visible price; ignore crossed-out / extension-converted JPY.
        price = _coerce_price(raw.get("current_price"))
        if price is None:
            price = _coerce_price(raw.get("price"))
        if price is None:
            _bump(reasons, "missing_or_invalid_price")
            rejected.append(f"item {index}: invalid price")
            continue
        currency = str(raw.get("currency") or "").strip().upper()
        if currency not in {"USD", "EUR", "GBP", "JPY"}:
            _bump(reasons, "ambiguous_currency")
            rejected.append(f"item {index}: ambiguous currency")
            continue
        product_id = str(raw.get("product_id") or "").strip()
        if url in seen:
            _bump(reasons, "duplicate")
            rejected.append(f"item {index}: duplicate")
            continue
        seen.add(url)
        brand = canonical_brand or str(raw.get("brand") or "").strip()
        condition = str(raw.get("condition") or "UNKNOWN").strip() or "UNKNOWN"
        category = str(raw.get("category") or "").strip()
        listings.append(
            AcquiredListing(
                external_id=product_id or _external_id_from_url(url),
                title=title,
                brand=brand,
                category=category or _infer_category(title),
                condition=condition,
                price=price,
                currency=currency,
                url=url,
                image_url=str(raw.get("image_url") or ""),
                retrieved_at=now,
                source=ALLOWED_MARKETPLACE,
                raw_title=meta_prefix + title,
                acquisition_status=AcquisitionStatus.LIVE,
            )
        )
    return listings, rejected, reasons


def _bump(reasons: dict[str, int], key: str) -> None:
    reasons[key] = reasons.get(key, 0) + 1


def _coerce_price(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return amount


def _external_id_from_url(url: str) -> str:
    path = url.rstrip("/").split("/")[-1]
    return path or url


def _infer_category(title: str) -> str:
    lowered = title.lower()
    if any(token in lowered for token in ("wallet", "card holder", "card case", "coin")):
        return "Wallet"
    if any(token in lowered for token in ("bag", "tote", "shoulder", "handbag", "hobo", "backpack")):
        return "Bag"
    return "Bag"
