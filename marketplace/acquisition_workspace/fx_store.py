"""Persist FX snapshots and last-known valid rates (not process memory only)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR
from marketplace.acquisition_workspace.fx_models import FxSnapshot

FX_DIR = BASE_DIR / "data" / "fx"
LATEST_RATES_PATH = FX_DIR / "latest_rates.json"
SNAPSHOTS_DIR = FX_DIR / "snapshots"
BATCH_LINKS_DIR = FX_DIR / "batch_links"
SESSIONS_DIR = FX_DIR / "sessions"


def _ensure_dirs() -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_LINKS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FX_DIR.mkdir(parents=True, exist_ok=True)


def save_snapshot(snapshot: FxSnapshot) -> Path:
    _ensure_dirs()
    path = SNAPSHOTS_DIR / f"{snapshot.snapshot_id}.json"
    path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if snapshot.session_id:
        link = SESSIONS_DIR / f"{snapshot.session_id}.json"
        link.write_text(
            json.dumps(
                {
                    "session_id": snapshot.session_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "linked_at": datetime.now(tz=UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return path


def load_snapshot(snapshot_id: str) -> FxSnapshot | None:
    sid = (snapshot_id or "").strip()
    if not sid:
        return None
    path = SNAPSHOTS_DIR / f"{sid}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return FxSnapshot.from_dict(raw)


def load_snapshot_for_session(session_id: str) -> FxSnapshot | None:
    sid = (session_id or "").strip()
    if not sid:
        return None
    link = SESSIONS_DIR / f"{sid}.json"
    if link.is_file():
        try:
            raw = json.loads(link.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                snap = load_snapshot(str(raw.get("snapshot_id") or ""))
                if snap is not None:
                    return snap
        except (OSError, json.JSONDecodeError):
            pass
    # Fallback: scan snapshots for matching session_id
    if not SNAPSHOTS_DIR.is_dir():
        return None
    for path in sorted(SNAPSHOTS_DIR.glob("fx-*.json"), reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and str(raw.get("session_id") or "") == sid:
            return FxSnapshot.from_dict(raw)
    return None


def link_batch_to_snapshot(batch_id: str, snapshot_id: str) -> None:
    bid = (batch_id or "").strip()
    sid = (snapshot_id or "").strip()
    if not bid or not sid:
        return
    _ensure_dirs()
    path = BATCH_LINKS_DIR / f"{bid}.json"
    path.write_text(
        json.dumps(
            {
                "workspace_batch_id": bid,
                "snapshot_id": sid,
                "linked_at": datetime.now(tz=UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_snapshot_for_batch(batch_id: str) -> FxSnapshot | None:
    bid = (batch_id or "").strip()
    if not bid:
        return None
    path = BATCH_LINKS_DIR / f"{bid}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return load_snapshot(str(raw.get("snapshot_id") or ""))


def save_latest_rates(
    *,
    rates: dict[str, Decimal],
    source_name: str,
    source_url: str,
    retrieved_at: str,
) -> None:
    _ensure_dirs()
    payload = {
        "rates": {key: format(value, "f") for key, value in rates.items()},
        "source_name": source_name,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "saved_at": datetime.now(tz=UTC).isoformat(),
    }
    LATEST_RATES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_latest_rates() -> dict[str, Any] | None:
    if not LATEST_RATES_PATH.is_file():
        return None
    try:
        raw = json.loads(LATEST_RATES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None
