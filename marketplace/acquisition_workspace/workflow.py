"""Operator workflow for sourcing candidates (status + notes).

Presentation/session organization only. Does not affect ranking or profit.
Persists to a JSON sidecar file — no SQLite schema changes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Iterable


class WorkflowStatus(StrEnum):
    """Operator sourcing workflow status.

    Future states (Purchased / Sold / Archived) can be appended here and
    registered in STATUS_DEFINITIONS without redesigning the UI.
    """

    UNCHECKED = "unchecked"
    REVIEWING = "reviewing"
    HOLD = "hold"
    PURCHASE_PLANNED = "purchase_planned"
    # Future-ready placeholders (not yet selectable in UI):
    # PURCHASED = "purchased"
    # SOLD = "sold"
    # ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class StatusDefinition:
    code: str
    label: str
    css_class: str
    selectable: bool = True


# Soft palette classes; add future codes here without template redesign.
STATUS_DEFINITIONS: tuple[StatusDefinition, ...] = (
    StatusDefinition("unchecked", "未確認", "status-unchecked"),
    StatusDefinition("reviewing", "検討中", "status-reviewing"),
    StatusDefinition("hold", "保留", "status-hold"),
    StatusDefinition("purchase_planned", "購入予定", "status-purchase-planned"),
    # Future examples (selectable=False until enabled):
    # StatusDefinition("purchased", "購入済", "status-purchased", selectable=False),
    # StatusDefinition("sold", "売却済", "status-sold", selectable=False),
    # StatusDefinition("archived", "アーカイブ", "status-archived", selectable=False),
)

STATUS_BY_CODE: dict[str, StatusDefinition] = {item.code: item for item in STATUS_DEFINITIONS}
DEFAULT_STATUS = WorkflowStatus.UNCHECKED.value
FILTER_ALL = "all"


def selectable_statuses() -> list[StatusDefinition]:
    return [item for item in STATUS_DEFINITIONS if item.selectable]


def status_label(code: str | None) -> str:
    definition = STATUS_BY_CODE.get(str(code or DEFAULT_STATUS), STATUS_BY_CODE[DEFAULT_STATUS])
    return definition.label


def status_css_class(code: str | None) -> str:
    definition = STATUS_BY_CODE.get(str(code or DEFAULT_STATUS), STATUS_BY_CODE[DEFAULT_STATUS])
    return definition.css_class


def normalize_status(code: str | None) -> str:
    raw = str(code or DEFAULT_STATUS).strip().lower()
    if raw in STATUS_BY_CODE and STATUS_BY_CODE[raw].selectable:
        return raw
    raise ValueError(f"unsupported workflow status: {code!r}")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class CandidateWorkflowState:
    candidate_id: str
    status: str = DEFAULT_STATUS
    notes: str = ""
    updated_at: str = ""

    def label(self) -> str:
        return status_label(self.status)

    def css_class(self) -> str:
        return status_css_class(self.status)


@dataclass
class CandidateWorkflowStore:
    """JSON sidecar store for operator workflow state."""

    storage_path: Path | None = None
    _records: dict[str, CandidateWorkflowState] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.storage_path and self.storage_path.exists():
            self._load()

    def get(self, candidate_id: str) -> CandidateWorkflowState:
        key = str(candidate_id or "").strip()
        if key in self._records:
            return self._records[key]
        return CandidateWorkflowState(candidate_id=key, status=DEFAULT_STATUS, notes="", updated_at="")

    def get_many(self, candidate_ids: Iterable[str]) -> dict[str, CandidateWorkflowState]:
        return {cid: self.get(cid) for cid in candidate_ids}

    def set_status(self, candidate_id: str, status: str) -> CandidateWorkflowState:
        normalized = normalize_status(status)
        current = self.get(candidate_id)
        updated = CandidateWorkflowState(
            candidate_id=current.candidate_id or candidate_id,
            status=normalized,
            notes=current.notes,
            updated_at=_utcnow_iso(),
        )
        self._records[updated.candidate_id] = updated
        self._persist()
        return updated

    def set_notes(self, candidate_id: str, notes: str) -> CandidateWorkflowState:
        current = self.get(candidate_id)
        updated = CandidateWorkflowState(
            candidate_id=current.candidate_id or candidate_id,
            status=current.status or DEFAULT_STATUS,
            notes=str(notes or ""),
            updated_at=_utcnow_iso(),
        )
        self._records[updated.candidate_id] = updated
        self._persist()
        return updated

    def update(
        self,
        candidate_id: str,
        *,
        status: str | None = None,
        notes: str | None = None,
    ) -> CandidateWorkflowState:
        current = self.get(candidate_id)
        next_status = normalize_status(status) if status is not None else (current.status or DEFAULT_STATUS)
        next_notes = current.notes if notes is None else str(notes)
        updated = CandidateWorkflowState(
            candidate_id=current.candidate_id or candidate_id,
            status=next_status,
            notes=next_notes,
            updated_at=_utcnow_iso(),
        )
        self._records[updated.candidate_id] = updated
        self._persist()
        return updated

    def _load(self) -> None:
        if not self.storage_path:
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        records = payload.get("candidates", payload) if isinstance(payload, dict) else {}
        if not isinstance(records, dict):
            return
        loaded: dict[str, CandidateWorkflowState] = {}
        for key, value in records.items():
            if not isinstance(value, dict):
                continue
            status = str(value.get("status") or DEFAULT_STATUS)
            if status not in STATUS_BY_CODE:
                status = DEFAULT_STATUS
            loaded[str(key)] = CandidateWorkflowState(
                candidate_id=str(value.get("candidate_id") or key),
                status=status,
                notes=str(value.get("notes") or ""),
                updated_at=str(value.get("updated_at") or ""),
            )
        self._records = loaded

    def _persist(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "candidates": {
                key: asdict(value)
                for key, value in sorted(self._records.items(), key=lambda item: item[0])
            }
        }
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def workflow_view(state: CandidateWorkflowState) -> dict[str, str]:
    """Template-friendly dict for one candidate."""
    return {
        "candidate_id": state.candidate_id,
        "status": state.status or DEFAULT_STATUS,
        "label": state.label(),
        "css_class": state.css_class(),
        "notes": state.notes or "",
        "updated_at": state.updated_at or "",
    }


def build_workflow_views(
    candidate_ids: Iterable[str],
    store: CandidateWorkflowStore,
) -> dict[str, dict[str, str]]:
    return {cid: workflow_view(store.get(cid)) for cid in candidate_ids}


def filter_choices() -> list[dict[str, str]]:
    choices = [{"code": FILTER_ALL, "label": "すべて"}]
    for item in selectable_statuses():
        choices.append({"code": item.code, "label": item.label})
    return choices
