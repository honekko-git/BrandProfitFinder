"""Deterministic bulk-acquisition session state (brand-independent)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from marketplace.acquisition_workspace.popular_brands import PopularBrand, resolve_selected_brands


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass
class BrandProgress:
    canonical_brand: str
    display_name: str
    fashionphile_search_url: str
    status: str = "pending"  # pending|active|importing|visible_complete|failed|skipped
    detected_count: int = 0
    imported_count: int = 0
    already_imported_count: int = 0
    remaining_count: int = 0
    within_budget_count: int = 0
    over_budget_count: int = 0
    currency_unknown_count: int = 0
    fx_unavailable_count: int = 0
    workspace_batch_id: str = ""
    source_page_url: str = ""
    error_message: str = ""
    completed_at: str = ""


@dataclass
class BulkAcquisitionSession:
    session_id: str
    selected_brands: list[str]
    brand_order: list[str]
    current_brand_index: int
    current_brand: str
    completed_brands: list[str]
    status: str  # active|paused|failed|complete|ended
    started_at: str
    last_updated_at: str
    workspace_batch_id: str = ""
    brands: dict[str, BrandProgress] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    user_message: str = ""
    budget_limit_jpy: int | None = None
    budget_preset: str = "none"
    fx_snapshot_id: str = ""
    fx_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BulkAcquisitionSession:
        brands_raw = raw.get("brands") or {}
        brands: dict[str, BrandProgress] = {}
        if isinstance(brands_raw, dict):
            for key, value in brands_raw.items():
                if not isinstance(value, dict):
                    continue
                brands[str(key)] = BrandProgress(
                    canonical_brand=str(value.get("canonical_brand") or key),
                    display_name=str(value.get("display_name") or key),
                    fashionphile_search_url=str(value.get("fashionphile_search_url") or ""),
                    status=str(value.get("status") or "pending"),
                    detected_count=int(value.get("detected_count") or 0),
                    imported_count=int(value.get("imported_count") or 0),
                    already_imported_count=int(value.get("already_imported_count") or 0),
                    remaining_count=int(value.get("remaining_count") or 0),
                    within_budget_count=int(value.get("within_budget_count") or 0),
                    over_budget_count=int(value.get("over_budget_count") or 0),
                    currency_unknown_count=int(value.get("currency_unknown_count") or 0),
                    fx_unavailable_count=int(value.get("fx_unavailable_count") or 0),
                    workspace_batch_id=str(value.get("workspace_batch_id") or ""),
                    source_page_url=str(value.get("source_page_url") or ""),
                    error_message=str(value.get("error_message") or ""),
                    completed_at=str(value.get("completed_at") or ""),
                )
        budget_raw = raw.get("budget_limit_jpy")
        budget_limit: int | None
        if budget_raw is None or budget_raw == "":
            budget_limit = None
        else:
            budget_limit = int(budget_raw)
        fx_summary = raw.get("fx_summary") if isinstance(raw.get("fx_summary"), dict) else {}
        return cls(
            session_id=str(raw.get("session_id") or ""),
            selected_brands=list(raw.get("selected_brands") or []),
            brand_order=list(raw.get("brand_order") or []),
            current_brand_index=int(raw.get("current_brand_index") or 0),
            current_brand=str(raw.get("current_brand") or ""),
            completed_brands=list(raw.get("completed_brands") or []),
            status=str(raw.get("status") or "ended"),
            started_at=str(raw.get("started_at") or ""),
            last_updated_at=str(raw.get("last_updated_at") or ""),
            workspace_batch_id=str(raw.get("workspace_batch_id") or ""),
            brands=brands,
            errors=list(raw.get("errors") or []),
            user_message=str(raw.get("user_message") or ""),
            budget_limit_jpy=budget_limit,
            budget_preset=str(raw.get("budget_preset") or "none"),
            fx_snapshot_id=str(raw.get("fx_snapshot_id") or ""),
            fx_summary=dict(fx_summary),
        )


def start_bulk_session(
    catalog: tuple[PopularBrand, ...] | list[PopularBrand],
    selected_canonicals: list[str],
    *,
    budget_limit_jpy: int | None = None,
    budget_preset: str = "none",
    fx_snapshot_id: str = "",
    fx_summary: dict[str, Any] | None = None,
) -> BulkAcquisitionSession:
    ordered = resolve_selected_brands(catalog, selected_canonicals)
    if not ordered:
        raise ValueError("ブランドを選択してください")
    session_id = f"bulk-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    brands = {
        item.canonical_brand: BrandProgress(
            canonical_brand=item.canonical_brand,
            display_name=item.display_name,
            fashionphile_search_url=item.fashionphile_search_url,
            status="active" if index == 0 else "pending",
        )
        for index, item in enumerate(ordered)
    }
    first = ordered[0]
    return BulkAcquisitionSession(
        session_id=session_id,
        selected_brands=[item.canonical_brand for item in ordered],
        brand_order=[item.canonical_brand for item in ordered],
        current_brand_index=0,
        current_brand=first.canonical_brand,
        completed_brands=[],
        status="active",
        started_at=_now(),
        last_updated_at=_now(),
        brands=brands,
        user_message=f"現在: {first.display_name}",
        budget_limit_jpy=budget_limit_jpy,
        budget_preset=budget_preset or "none",
        fx_snapshot_id=fx_snapshot_id or "",
        fx_summary=dict(fx_summary or {}),
    )


def current_search_url(session: BulkAcquisitionSession) -> str:
    progress = session.brands.get(session.current_brand)
    if progress is None:
        return ""
    return progress.fashionphile_search_url


def apply_import_result(
    session: BulkAcquisitionSession,
    *,
    detected_count: int,
    imported_this_run: int,
    already_imported_count: int,
    remaining_count: int,
    workspace_batch_id: str,
    source_page_url: str,
    within_budget_count: int = 0,
    over_budget_count: int = 0,
    currency_unknown_count: int = 0,
    fx_unavailable_count: int = 0,
) -> BulkAcquisitionSession:
    """Update current brand from backend-confirmed import counts."""
    brand = session.current_brand
    progress = session.brands[brand]
    progress.detected_count = max(progress.detected_count, int(detected_count))
    progress.imported_count = max(0, int(detected_count) - int(remaining_count))
    progress.already_imported_count = int(already_imported_count)
    progress.remaining_count = max(0, int(remaining_count))
    progress.within_budget_count = max(progress.within_budget_count, int(within_budget_count))
    progress.over_budget_count = max(progress.over_budget_count, int(over_budget_count))
    progress.currency_unknown_count = max(
        progress.currency_unknown_count, int(currency_unknown_count)
    )
    progress.fx_unavailable_count = max(progress.fx_unavailable_count, int(fx_unavailable_count))
    progress.source_page_url = source_page_url or progress.source_page_url
    if workspace_batch_id:
        progress.workspace_batch_id = workspace_batch_id
        session.workspace_batch_id = workspace_batch_id
    progress.status = "importing"
    if progress.remaining_count == 0 and progress.detected_count > 0:
        progress.status = "visible_complete"
        progress.completed_at = _now()
        if brand not in session.completed_brands:
            session.completed_brands.append(brand)
        session.user_message = (
            f"{progress.display_name}: 現在表示されている商品をすべて取り込みました。"
        )
    elif progress.remaining_count > 0:
        session.user_message = (
            f"{progress.display_name}: {progress.imported_count}件取込済 / 残り{progress.remaining_count}件"
        )
    session.last_updated_at = _now()
    return session


def mark_brand_failed(session: BulkAcquisitionSession, message: str) -> BulkAcquisitionSession:
    progress = session.brands[session.current_brand]
    progress.status = "failed"
    progress.error_message = message
    session.status = "failed"
    session.errors.append(f"{progress.canonical_brand}: {message}")
    session.user_message = message
    session.last_updated_at = _now()
    return session


def retry_failed_brand(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    progress = session.brands[session.current_brand]
    if progress.status != "failed":
        return session
    progress.status = "active"
    progress.error_message = ""
    session.status = "active"
    session.user_message = f"現在: {progress.display_name}"
    session.last_updated_at = _now()
    return session


def skip_current_brand(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    progress = session.brands[session.current_brand]
    progress.status = "skipped"
    progress.completed_at = _now()
    return advance_to_next_brand(session)


def advance_to_next_brand(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    """Move to the next selected brand. Completes the session when none remain."""
    current = session.brands.get(session.current_brand)
    if current and current.status not in {"visible_complete", "skipped", "failed"}:
        if current.remaining_count == 0 and current.detected_count > 0:
            current.status = "visible_complete"
            if session.current_brand not in session.completed_brands:
                session.completed_brands.append(session.current_brand)
    next_index = session.current_brand_index + 1
    if next_index >= len(session.brand_order):
        session.status = "complete"
        session.current_brand = ""
        session.user_message = "選択したブランドの取り込みが完了しました。"
        session.last_updated_at = _now()
        return session
    session.current_brand_index = next_index
    session.current_brand = session.brand_order[next_index]
    nxt = session.brands[session.current_brand]
    nxt.status = "active"
    session.status = "active"
    session.user_message = f"現在: {nxt.display_name}"
    session.last_updated_at = _now()
    return session


def pause_session(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    session.status = "paused"
    session.user_message = "一括取得を一時停止しました。"
    session.last_updated_at = _now()
    return session


def resume_session(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    if session.status == "complete":
        return session
    session.status = "active"
    current = session.brands.get(session.current_brand)
    session.user_message = f"現在: {current.display_name}" if current else "一括取得を再開しました。"
    session.last_updated_at = _now()
    return session


def end_session(session: BulkAcquisitionSession) -> BulkAcquisitionSession:
    session.status = "ended"
    session.user_message = "一括取得を終了しました。"
    session.last_updated_at = _now()
    return session


def progress_summary(session: BulkAcquisitionSession) -> dict[str, Any]:
    total = len(session.brand_order)
    completed = len(
        [
            name
            for name in session.brand_order
            if session.brands[name].status in {"visible_complete", "skipped"}
        ]
    )
    return {
        "completed_count": completed,
        "total_count": total,
        "current_brand": session.current_brand,
        "status": session.status,
        "workspace_batch_id": session.workspace_batch_id,
        "user_message": session.user_message,
    }
