"""Session-level FX snapshot models for bulk acquisition budget filtering."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4


class FxFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MANUAL = "MANUAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNUSABLE = "UNUSABLE"


REQUIRED_CURRENCIES = ("USD", "EUR", "GBP")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None
    if amount <= 0:
        return None
    return amount


@dataclass
class FxSnapshot:
    """Immutable FX rates for one bulk-acquisition session."""

    snapshot_id: str
    session_id: str
    base_currency: str
    rates: dict[str, str]  # USD_TO_JPY etc. as Decimal strings
    source_name: str
    source_url: str
    retrieved_at: str
    freshness_status: str
    fallback_used: bool
    fallback_reason: str
    stored_rate_age_seconds: int | None
    safe_rate_adjustment: str | None
    warnings: list[str]
    created_at: str
    unavailable_currencies: list[str] = field(default_factory=list)
    user_message: str = ""

    def rate_for(self, currency: str) -> Decimal | None:
        code = str(currency or "").strip().upper()
        if code == "JPY":
            return Decimal("1")
        key = f"{code}_TO_JPY"
        if key not in self.rates:
            return None
        if code in {c.upper() for c in self.unavailable_currencies}:
            return None
        return _dec(self.rates.get(key))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FxSnapshot:
        rates_raw = raw.get("rates") or {}
        rates: dict[str, str] = {}
        if isinstance(rates_raw, dict):
            for key, value in rates_raw.items():
                amount = _dec(value)
                if amount is not None:
                    rates[str(key)] = format(amount, "f")
        age = raw.get("stored_rate_age_seconds")
        return cls(
            snapshot_id=str(raw.get("snapshot_id") or ""),
            session_id=str(raw.get("session_id") or ""),
            base_currency=str(raw.get("base_currency") or "JPY"),
            rates=rates,
            source_name=str(raw.get("source_name") or ""),
            source_url=str(raw.get("source_url") or ""),
            retrieved_at=str(raw.get("retrieved_at") or ""),
            freshness_status=str(raw.get("freshness_status") or FxFreshness.UNAVAILABLE.value),
            fallback_used=bool(raw.get("fallback_used")),
            fallback_reason=str(raw.get("fallback_reason") or ""),
            stored_rate_age_seconds=int(age) if age is not None and str(age).strip() != "" else None,
            safe_rate_adjustment=(
                str(raw["safe_rate_adjustment"])
                if raw.get("safe_rate_adjustment") not in (None, "")
                else None
            ),
            warnings=[str(item) for item in (raw.get("warnings") or [])],
            created_at=str(raw.get("created_at") or ""),
            unavailable_currencies=[str(item) for item in (raw.get("unavailable_currencies") or [])],
            user_message=str(raw.get("user_message") or ""),
        )


def new_snapshot_id() -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
    return f"fx-{stamp}-{uuid4().hex[:8]}"


def build_snapshot(
    *,
    session_id: str,
    rates: dict[str, Decimal],
    source_name: str,
    source_url: str = "",
    retrieved_at: str | None = None,
    freshness_status: str = FxFreshness.FRESH.value,
    fallback_used: bool = False,
    fallback_reason: str = "",
    stored_rate_age_seconds: int | None = None,
    safe_rate_adjustment: str | None = None,
    warnings: list[str] | None = None,
    unavailable_currencies: list[str] | None = None,
    user_message: str = "",
    snapshot_id: str | None = None,
) -> FxSnapshot:
    now = _now()
    normalized: dict[str, str] = {}
    for key, value in rates.items():
        amount = _dec(value)
        if amount is None:
            continue
        normalized[str(key)] = format(amount, "f")
    return FxSnapshot(
        snapshot_id=snapshot_id or new_snapshot_id(),
        session_id=session_id,
        base_currency="JPY",
        rates=normalized,
        source_name=source_name,
        source_url=source_url,
        retrieved_at=retrieved_at or now,
        freshness_status=freshness_status,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        stored_rate_age_seconds=stored_rate_age_seconds,
        safe_rate_adjustment=safe_rate_adjustment,
        warnings=list(warnings or []),
        created_at=now,
        unavailable_currencies=list(unavailable_currencies or []),
        user_message=user_message,
    )
