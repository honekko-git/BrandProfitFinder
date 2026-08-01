"""Version 1.0 real operational audit for overseas acquisition sources.

LIVE HTTP/browser acquisition only. No saved HTML, fixtures, or fake adapters.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "version1_operational_audit_live.json"
OUT_MD = ROOT / "output" / "version1_operational_audit_live.md"

KEYWORDS = {
    "Fashionphile": "PRADA",
    "Rebag": "Chanel",
    "The RealReal": "Gucci",
    "Vestiaire Collective": "Louis Vuitton",
}


@dataclass
class MarketplaceAudit:
    marketplace: str
    keyword: str = ""
    search_url: str = ""
    http_status: int | None = None
    final_url: str = ""
    redirects_observed: bool = False
    cloudflare_detected: bool = False
    captcha_detected: bool = False
    login_required: bool = False
    js_rendering_required: bool = True
    live_products_returned: int = 0
    acquisition_usable: bool = False
    acquisition_status: str = ""
    acquisition_detail: str = ""
    products_detected: int = 0
    products_parsed: int = 0
    missing_fields: list[str] = field(default_factory=list)
    sample_titles: list[str] = field(default_factory=list)
    sample_urls: list[str] = field(default_factory=list)
    sample_prices: list[str] = field(default_factory=list)
    sample_brands: list[str] = field(default_factory=list)
    images_present: int = 0
    parse_failure_reason: str = ""
    pipeline_stage_reached: str = "none"
    pipeline_ok: bool = False
    pipeline_detail: str = ""
    operational: str = "NO"  # YES | PARTIAL | NO
    operational_why: str = ""
    blocking_reason: str = ""
    required_engineering_work: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _detect_page_signals(html: str, status_code: int | None) -> dict[str, bool]:
    text = (html or "").lower()
    return {
        "cloudflare_detected": any(
            token in text for token in ("cf-ray", "cloudflare", "cf-challenge", "just a moment", "checking your browser")
        )
        or (status_code in {403, 503}),
        "captcha_detected": any(
            token in text for token in ("captcha", "hcaptcha", "turnstile", "verify you are human", "cf-challenge")
        ),
        "login_required": any(
            token in text for token in ("sign in", "log in", "login", "create account", "auth0")
        )
        and "product" not in text[:2000],
    }


def _missing_listing_fields(listing) -> list[str]:
    missing = []
    if not getattr(listing, "title", None):
        missing.append("title")
    if not getattr(listing, "url", None):
        missing.append("url")
    if getattr(listing, "price", None) is None:
        missing.append("price")
    if not getattr(listing, "brand", None):
        missing.append("brand")
    # image is optional on AcquiredListing; track if attribute exists
    image = getattr(listing, "image_url", None) or getattr(listing, "image", None)
    if not image:
        missing.append("image")
    return missing


def audit_fashionphile(result: MarketplaceAudit) -> None:
    from marketplace.browser_acquisition.browser_session import BrowserSession
    from marketplace.browser_acquisition.fashionphile_acquirer import (
        FASHIONPHILE_SEARCH_URL,
        FashionphileAcquirer,
        parse_fashionphile_html,
    )

    keyword = KEYWORDS["Fashionphile"]
    result.keyword = keyword
    result.search_url = FASHIONPHILE_SEARCH_URL.format(query=quote_plus(keyword))
    session = BrowserSession(headless=True, timeout_ms=45_000)
    fetch = session.fetch_html(result.search_url)
    result.http_status = fetch.status_code
    result.final_url = fetch.url
    result.redirects_observed = (fetch.url or "").rstrip("/") != result.search_url.rstrip("/")
    signals = _detect_page_signals(fetch.html or "", fetch.status_code)
    result.cloudflare_detected = signals["cloudflare_detected"]
    result.captcha_detected = signals["captcha_detected"] or bool(fetch.blocked_reason and "CAPTCHA" in fetch.blocked_reason.upper())
    result.login_required = signals["login_required"]
    result.evidence["fetch_blocked_reason"] = fetch.blocked_reason
    result.evidence["html_bytes"] = len(fetch.html or "")

    if fetch.blocked_reason:
        result.acquisition_status = "BLOCKED"
        result.acquisition_detail = fetch.blocked_reason
        result.blocking_reason = fetch.blocked_reason
        result.live_products_returned = 0
        result.acquisition_usable = False
    else:
        listings = parse_fashionphile_html(fetch.html or "")
        result.products_detected = len(listings)
        result.products_parsed = len(listings)
        result.live_products_returned = len(listings)
        result.acquisition_status = "LIVE" if listings else "EMPTY"
        result.acquisition_usable = bool(listings)
        _fill_parse_samples(result, listings)

    # Also exercise official acquirer path (no html injection).
    try:
        acq = FashionphileAcquirer(purchase_limit=20, browser=session).search_keyword(keyword, limit=20)
        result.evidence["acquirer_status"] = acq.status.value
        result.evidence["acquirer_listing_count"] = len(acq.listings)
        result.evidence["acquirer_detail"] = acq.detail
        if not result.live_products_returned and acq.listings:
            result.live_products_returned = len(acq.listings)
            result.products_parsed = len(acq.listings)
            result.acquisition_usable = True
            result.acquisition_status = acq.status.value
            _fill_parse_samples(result, list(acq.listings))
        if not result.acquisition_usable and acq.blocking_reason:
            result.blocking_reason = acq.blocking_reason or result.blocking_reason
            result.acquisition_detail = acq.detail or result.acquisition_detail
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"acquirer:{type(exc).__name__}:{exc}")
        result.blocking_reason = result.blocking_reason or type(exc).__name__


def audit_rebag(result: MarketplaceAudit) -> None:
    from marketplace.browser_acquisition.browser_session import BrowserSession
    from marketplace.browser_acquisition.rebag_acquirer import REBAG_SEARCH_URL, RebagAcquirer, parse_rebag_html

    keyword = KEYWORDS["Rebag"]
    result.keyword = keyword
    result.search_url = REBAG_SEARCH_URL.format(query=quote_plus(keyword))

    session = BrowserSession(headless=True, timeout_ms=45_000)
    fetch = session.fetch_html(result.search_url)
    result.http_status = fetch.status_code
    result.final_url = fetch.url
    result.redirects_observed = (fetch.url or "").rstrip("/") != result.search_url.rstrip("/")
    signals = _detect_page_signals(fetch.html or "", fetch.status_code)
    result.cloudflare_detected = signals["cloudflare_detected"]
    result.captcha_detected = signals["captcha_detected"] or bool(
        fetch.blocked_reason and "CAPTCHA" in (fetch.blocked_reason or "").upper()
    )
    result.login_required = signals["login_required"]
    result.evidence["fetch_blocked_reason"] = fetch.blocked_reason
    result.evidence["html_bytes"] = len(fetch.html or "")

    if fetch.html and not fetch.blocked_reason:
        pre = parse_rebag_html(fetch.html)
        result.evidence["direct_parse_count"] = len(pre)

    try:
        acq = RebagAcquirer(purchase_limit=20, browser=session).search_keyword(keyword, limit=20)
        result.acquisition_status = acq.status.value
        result.acquisition_detail = acq.detail or ""
        result.live_products_returned = len(acq.listings)
        result.products_detected = len(acq.listings)
        result.products_parsed = len(acq.listings)
        result.acquisition_usable = bool(acq.listings)
        if acq.listings:
            _fill_parse_samples(result, list(acq.listings))
        else:
            result.blocking_reason = acq.blocking_reason or fetch.blocked_reason or "No products"
            result.parse_failure_reason = acq.detail or result.blocking_reason
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"acquirer:{type(exc).__name__}:{exc}")
        result.acquisition_status = "FAILED"
        result.blocking_reason = type(exc).__name__
        result.acquisition_detail = str(exc)


def audit_realreal(result: MarketplaceAudit) -> None:
    from marketplace.browser_acquisition.browser_session import BrowserSession
    from marketplace.browser_acquisition.realreal_acquirer import (
        REALREAL_SEARCH_URL,
        RealRealAcquirer,
        parse_realreal_html,
    )

    keyword = KEYWORDS["The RealReal"]
    result.keyword = keyword
    result.search_url = REALREAL_SEARCH_URL.format(query=quote_plus(keyword))

    session = BrowserSession(headless=True, timeout_ms=45_000)
    fetch = session.fetch_html(result.search_url)
    result.http_status = fetch.status_code
    result.final_url = fetch.url
    result.redirects_observed = (fetch.url or "").rstrip("/") != result.search_url.rstrip("/")
    signals = _detect_page_signals(fetch.html or "", fetch.status_code)
    result.cloudflare_detected = signals["cloudflare_detected"]
    result.captcha_detected = signals["captcha_detected"] or bool(
        fetch.blocked_reason and "CAPTCHA" in (fetch.blocked_reason or "").upper()
    )
    result.login_required = signals["login_required"]
    result.evidence["fetch_blocked_reason"] = fetch.blocked_reason
    result.evidence["html_bytes"] = len(fetch.html or "")

    if fetch.html and not fetch.blocked_reason:
        pre = parse_realreal_html(fetch.html)
        result.evidence["direct_parse_count"] = len(pre)

    try:
        acq = RealRealAcquirer(purchase_limit=20, browser=session).search_keyword(keyword, limit=20)
        result.acquisition_status = acq.status.value
        result.acquisition_detail = acq.detail or ""
        result.live_products_returned = len(acq.listings)
        result.products_detected = len(acq.listings)
        result.products_parsed = len(acq.listings)
        result.acquisition_usable = bool(acq.listings)
        if acq.listings:
            _fill_parse_samples(result, list(acq.listings))
        else:
            result.blocking_reason = acq.blocking_reason or fetch.blocked_reason or "No products"
            result.parse_failure_reason = acq.detail or result.blocking_reason
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"acquirer:{type(exc).__name__}:{exc}")
        result.acquisition_status = "FAILED"
        result.blocking_reason = type(exc).__name__
        result.acquisition_detail = str(exc)


def audit_vestiaire(result: MarketplaceAudit) -> None:
    from marketplace.browser_acquisition.browser_session import BrowserSession
    from marketplace.browser_acquisition.vestiaire_acquirer import (
        VESTIAIRE_SEARCH_URL,
        VestiaireAcquirer,
        parse_vestiaire_html,
    )

    keyword = KEYWORDS["Vestiaire Collective"]
    result.keyword = keyword
    result.search_url = VESTIAIRE_SEARCH_URL.format(query=quote_plus(keyword))

    session = BrowserSession(headless=True, timeout_ms=45_000)
    fetch = session.fetch_html(result.search_url)
    result.http_status = fetch.status_code
    result.final_url = fetch.url
    result.redirects_observed = (fetch.url or "").rstrip("/") != result.search_url.rstrip("/")
    signals = _detect_page_signals(fetch.html or "", fetch.status_code)
    result.cloudflare_detected = signals["cloudflare_detected"]
    result.captcha_detected = signals["captcha_detected"] or bool(
        fetch.blocked_reason and "CAPTCHA" in (fetch.blocked_reason or "").upper()
    )
    result.login_required = signals["login_required"]
    result.evidence["fetch_blocked_reason"] = fetch.blocked_reason
    result.evidence["html_bytes"] = len(fetch.html or "")

    if fetch.html and not fetch.blocked_reason:
        pre = parse_vestiaire_html(fetch.html)
        result.evidence["direct_parse_count"] = len(pre)

    try:
        acq = VestiaireAcquirer(purchase_limit=20, browser=session).search_keyword(keyword, limit=20)
        result.acquisition_status = acq.status.value
        result.acquisition_detail = acq.detail or ""
        result.live_products_returned = len(acq.listings)
        result.products_detected = len(acq.listings)
        result.products_parsed = len(acq.listings)
        result.acquisition_usable = bool(acq.listings)
        if acq.listings:
            _fill_parse_samples(result, list(acq.listings))
        else:
            result.blocking_reason = acq.blocking_reason or fetch.blocked_reason or "No products"
            result.parse_failure_reason = acq.detail or result.blocking_reason
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"acquirer:{type(exc).__name__}:{exc}")
        result.acquisition_status = "FAILED"
        result.blocking_reason = type(exc).__name__
        result.acquisition_detail = str(exc)


def _fill_parse_samples(result: MarketplaceAudit, listings: list) -> None:
    missing_counter: dict[str, int] = {}
    images = 0
    for item in listings:
        for field_name in _missing_listing_fields(item):
            missing_counter[field_name] = missing_counter.get(field_name, 0) + 1
        if getattr(item, "image_url", None) or getattr(item, "image", None):
            images += 1
    result.images_present = images
    result.missing_fields = [f"{k}:{v}/{len(listings)}" for k, v in sorted(missing_counter.items())]
    result.sample_titles = [str(getattr(x, "title", ""))[:80] for x in listings[:5]]
    result.sample_urls = [str(getattr(x, "url", ""))[:120] for x in listings[:5]]
    result.sample_prices = [f"{getattr(x, 'price', '')} {getattr(x, 'currency', '')}".strip() for x in listings[:5]]
    result.sample_brands = [str(getattr(x, "brand", "")) for x in listings[:5]]
    if listings and missing_counter.get("title") == len(listings):
        result.parse_failure_reason = "All listings missing title"
    elif not listings:
        result.parse_failure_reason = result.parse_failure_reason or "Zero listings parsed from live HTML"


def run_profit_pipeline_if_possible(result: MarketplaceAudit, listings: list | None = None) -> None:
    """Run production batch profit path only when live listings exist."""
    if not result.acquisition_usable or result.live_products_returned <= 0:
        result.pipeline_stage_reached = "acquisition"
        result.pipeline_ok = False
        result.pipeline_detail = "Pipeline not started: no live acquired products"
        return

    from tempfile import TemporaryDirectory

    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

    # Convert acquired listings through the real intake modules without html=.
    try:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "audit.db"
            service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db))
            imported = _import_live_into_workspace(result.marketplace, service, result.keyword)
            result.pipeline_stage_reached = "normalization"
            if not imported or not imported.get("batch_id"):
                result.pipeline_ok = False
                result.pipeline_detail = f"Import failed: {imported}"
                return
            result.pipeline_stage_reached = "import"
            batch_id = imported["batch_id"]
            _, rows = service.get_batch(batch_id)
            if not rows:
                result.pipeline_ok = False
                result.pipeline_detail = "No workspace rows after import"
                return
            result.pipeline_stage_reached = "matching_profit"
            # Bound Yahoo work; still production path.
            service.select_all_eligible(batch_id)
            _, selected = service.get_batch(batch_id)
            # Keep first 2 only for audit runtime.
            keep = {item.candidate_id for item in selected[:2]}
            for item in selected:
                if item.candidate_id not in keep:
                    service.select_candidate(batch_id, item.candidate_id, selected=False)
            service.run_batch_profit(batch_id, cost_profile_name="standard", use_cache=True)
            _, after = service.get_batch(batch_id)
            profit_rows = [r for r in after if r.last_net_profit is not None or r.last_decision]
            result.pipeline_stage_reached = "ranking"
            result.pipeline_ok = bool(profit_rows) or any(r.last_profit_checked_at for r in after)
            result.pipeline_detail = (
                f"batch={batch_id}; rows={len(after)}; profit_checked="
                f"{sum(1 for r in after if r.last_profit_checked_at)}; "
                f"decisions={[r.last_decision for r in after[:5]]}"
            )
            result.evidence["pipeline"] = {
                "batch_id": batch_id,
                "row_count": len(after),
                "profit_checked": sum(1 for r in after if r.last_profit_checked_at),
            }
    except Exception as exc:  # noqa: BLE001
        result.pipeline_ok = False
        result.pipeline_detail = f"{type(exc).__name__}: {exc}"
        result.errors.append(traceback.format_exc()[-1000:])


def _import_live_into_workspace(marketplace: str, service, keyword: str) -> dict:
    if marketplace == "Fashionphile":
        from marketplace.acquisition_workspace.live_fashionphile_intake import import_fashionphile_keyword

        out = import_fashionphile_keyword(service, keyword, limit=5, html=None, run_profit=False)
        return {"batch_id": out.batch_id, "count": out.listing_count, "status": out.status, "detail": out.detail}
    if marketplace == "Rebag":
        from marketplace.acquisition_workspace.live_rebag_intake import import_rebag_keyword

        out = import_rebag_keyword(service, keyword, limit=5, html=None, run_profit=False)
        return {"batch_id": out.batch_id, "count": out.listing_count, "status": out.status, "detail": out.detail}
    if marketplace == "The RealReal":
        from marketplace.acquisition_workspace.live_realreal_intake import import_realreal_keyword

        out = import_realreal_keyword(service, keyword, limit=5, html=None, run_profit=False)
        return {"batch_id": out.batch_id, "count": out.listing_count, "status": out.status, "detail": out.detail}
    if marketplace == "Vestiaire Collective":
        from marketplace.acquisition_workspace.live_vestiaire_intake import import_vestiaire_keyword

        out = import_vestiaire_keyword(service, keyword, limit=5, html=None, run_profit=False)
        return {"batch_id": out.batch_id, "count": out.listing_count, "status": out.status, "detail": out.detail}
    return {}


def classify_operational(result: MarketplaceAudit) -> None:
    if result.acquisition_usable and result.live_products_returned > 0 and result.pipeline_ok:
        result.operational = "YES"
        result.operational_why = (
            "Normal live acquisition returned products and the profit/ranking pipeline completed."
        )
        result.required_engineering_work = "No changes required"
        result.blocking_reason = result.blocking_reason or ""
        return
    if result.acquisition_usable and result.live_products_returned > 0 and not result.pipeline_ok:
        result.operational = "PARTIAL"
        result.operational_why = (
            "Live products were acquired, but the profit pipeline did not complete successfully."
        )
        result.required_engineering_work = "Fix domestic comparable / profit pipeline failures for live rows"
        return
    # acquisition failed
    reason = result.blocking_reason or result.acquisition_detail or result.parse_failure_reason or "Unknown"
    upper = reason.upper()
    if "CAPTCHA" in upper or "HCAPTCHA" in upper or "TURNSTILE" in upper:
        label = "CAPTCHA"
        work = "Browser automation with human CAPTCHA solve / persistent browser profile, or Chrome Extension capture"
    elif "CLOUDFLARE" in upper or "CF-CHALLENGE" in upper:
        label = "Cloudflare"
        work = "Browser automation with challenge clearance / residential session support"
    elif "LOGIN" in upper or "AUTH" in upper:
        label = "Authentication"
        work = "Login session support"
    elif "TIMEOUT" in upper:
        label = "Timeout"
        work = "Retry/timeout tuning and possibly headed browser"
    elif "SELECTOR" in upper or "NO PRODUCT" in upper or "NO FASHIONPHILE" in upper or "NO REBAG" in upper:
        label = "Parser failure / DOM change / Bot protection"
        work = "Parser update and/or headed Playwright against post-challenge DOM"
    else:
        label = reason.split(":")[0] if reason else "Other"
        work = "Investigate live blocker; likely browser automation or session support"
    result.operational = "NO"
    result.blocking_reason = label if not result.blocking_reason else result.blocking_reason
    result.operational_why = (
        f"A normal end user cannot complete live acquisition via the app. Evidence: "
        f"status={result.acquisition_status}, products={result.live_products_returned}, detail={result.acquisition_detail or reason}"
    )
    result.required_engineering_work = work


def main() -> None:
    audits: list[MarketplaceAudit] = []
    runners = [
        ("Fashionphile", audit_fashionphile),
        ("Rebag", audit_rebag),
        ("The RealReal", audit_realreal),
        ("Vestiaire Collective", audit_vestiaire),
    ]
    for name, fn in runners:
        print(f"=== AUDIT {name} ===", flush=True)
        item = MarketplaceAudit(marketplace=name)
        try:
            fn(item)
        except Exception as exc:  # noqa: BLE001
            item.errors.append(traceback.format_exc()[-1500:])
            item.acquisition_status = "FAILED"
            item.blocking_reason = type(exc).__name__
            item.acquisition_detail = str(exc)
        try:
            run_profit_pipeline_if_possible(item)
        except Exception as exc:  # noqa: BLE001
            item.pipeline_ok = False
            item.pipeline_detail = f"{type(exc).__name__}: {exc}"
            item.errors.append(traceback.format_exc()[-1000:])
        classify_operational(item)
        audits.append(item)
        print(
            json.dumps(
                {
                    "marketplace": name,
                    "live_products": item.live_products_returned,
                    "status": item.acquisition_status,
                    "operational": item.operational,
                    "blocking": item.blocking_reason,
                    "pipeline_ok": item.pipeline_ok,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    failed = [a.marketplace for a in audits if a.operational != "YES"]
    decision = "GO" if not failed else "NO-GO"
    summary = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "mode": "LIVE_ONLY_NO_FIXTURES_NO_SAVED_HTML",
        "decision": decision,
        "not_operationally_complete_because": (
            None
            if decision == "GO"
            else (
                "Version 1.0 is NOT operationally complete because real acquisition is unavailable "
                f"for the following marketplaces: {', '.join(failed)}"
            )
        ),
        "marketplaces": [asdict(a) for a in audits],
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(_to_markdown(summary, audits), encoding="utf-8")
    print("WROTE", OUT)
    print("WROTE", OUT_MD)
    print("DECISION", decision)


def _to_markdown(summary: dict, audits: list[MarketplaceAudit]) -> str:
    lines = [
        "# Version 1.0 Operational Audit (LIVE only)",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"Decision: **{summary['decision']}**",
        "",
    ]
    if summary.get("not_operationally_complete_because"):
        lines.append(summary["not_operationally_complete_because"])
        lines.append("")
    lines.extend(
        [
            "| Marketplace | Live Acquisition | Parsing | Profit Pipeline | Operational | Blocking Reason | Required Engineering Work |",
            "|--------------|-----------------|----------|-----------------|-------------|-----------------|---------------------------|",
        ]
    )
    for a in audits:
        live = f"{a.live_products_returned} ({a.acquisition_status})"
        parsing = f"{a.products_parsed}/{a.products_detected}" if a.products_detected or a.products_parsed else "0"
        profit = "OK" if a.pipeline_ok else f"FAIL@{a.pipeline_stage_reached}"
        lines.append(
            f"| {a.marketplace} | {live} | {parsing} | {profit} | {a.operational} | "
            f"{a.blocking_reason or '-'} | {a.required_engineering_work} |"
        )
    lines.append("")
    for a in audits:
        lines.extend(
            [
                f"## {a.marketplace}",
                "",
                f"- Keyword: `{a.keyword}`",
                f"- Search URL: `{a.search_url}`",
                f"- Final URL: `{a.final_url}`",
                f"- HTTP status: `{a.http_status}`",
                f"- Redirects: `{a.redirects_observed}`",
                f"- Cloudflare: `{a.cloudflare_detected}`",
                f"- CAPTCHA: `{a.captcha_detected}`",
                f"- Login required: `{a.login_required}`",
                f"- JS rendering required: `{a.js_rendering_required}`",
                f"- Live products returned: `{a.live_products_returned}`",
                f"- Acquisition usable: `{a.acquisition_usable}`",
                f"- Detail: {a.acquisition_detail or '-'}",
                f"- Missing fields: {a.missing_fields or '-'}",
                f"- Sample titles: {a.sample_titles or '-'}",
                f"- Sample URLs: {a.sample_urls or '-'}",
                f"- Sample prices: {a.sample_prices or '-'}",
                f"- Sample brands: {a.sample_brands or '-'}",
                f"- Images present: `{a.images_present}`",
                f"- Pipeline: `{a.pipeline_stage_reached}` ok={a.pipeline_ok} — {a.pipeline_detail}",
                f"- Operational: **{a.operational}** — {a.operational_why}",
                f"- Blocking reason: `{a.blocking_reason or '-'}`",
                f"- Required engineering work: {a.required_engineering_work}",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
