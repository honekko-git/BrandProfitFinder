"""Live FX acquisition with stored/manual fallback (server-side only)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable

from marketplace.acquisition_workspace.fx_config import (
    frankfurter_base_url,
    fresh_max_age_seconds,
    live_fx_disabled,
    provider_max_retries,
    provider_timeout_seconds,
    stale_max_age_seconds,
)
from marketplace.acquisition_workspace.fx_models import (
    REQUIRED_CURRENCIES,
    FxFreshness,
    FxSnapshot,
    build_snapshot,
)
from marketplace.acquisition_workspace.fx_store import (
    load_latest_rates,
    save_latest_rates,
    save_snapshot,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FxAcquireResult:
    ok: bool
    snapshot: FxSnapshot | None
    user_message: str
    failure_reason: str = ""


def classify_freshness(age_seconds: int | None, *, manual: bool = False) -> str:
    if manual:
        return FxFreshness.MANUAL.value
    if age_seconds is None:
        return FxFreshness.UNAVAILABLE.value
    if age_seconds < 0:
        return FxFreshness.UNUSABLE.value
    if age_seconds <= fresh_max_age_seconds():
        return FxFreshness.FRESH.value
    if age_seconds <= stale_max_age_seconds():
        return FxFreshness.STALE.value
    return FxFreshness.UNUSABLE.value


def parse_timestamp(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def age_seconds_since(retrieved_at: str, *, now: datetime | None = None) -> int | None:
    dt = parse_timestamp(retrieved_at)
    if dt is None:
        return None
    current = now or datetime.now(tz=UTC)
    return max(0, int((current - dt).total_seconds()))


def validate_rates(rates: dict[str, Decimal]) -> tuple[dict[str, Decimal], list[str], str]:
    """Return (valid_rates, unavailable, error). Reject zero/negative/missing keys."""
    valid: dict[str, Decimal] = {}
    unavailable: list[str] = []
    for code in REQUIRED_CURRENCIES:
        key = f"{code}_TO_JPY"
        amount = rates.get(key)
        if amount is None:
            unavailable.append(code)
            continue
        try:
            value = Decimal(str(amount))
        except Exception:  # noqa: BLE001
            return {}, list(REQUIRED_CURRENCIES), f"malformed rate for {code}"
        if value <= 0:
            return {}, list(REQUIRED_CURRENCIES), f"non-positive rate for {code}"
        valid[key] = value
    if not valid:
        return {}, list(REQUIRED_CURRENCIES), "no usable currency rates"
    return valid, unavailable, ""


def _manual_rates_from_env() -> dict[str, Decimal]:
    mapping = {
        "USD_TO_JPY": os.getenv("USD_JPY_EXCHANGE_RATE", "").strip(),
        "EUR_TO_JPY": os.getenv("EUR_JPY_EXCHANGE_RATE", "").strip(),
        "GBP_TO_JPY": os.getenv("GBP_JPY_EXCHANGE_RATE", "").strip(),
    }
    out: dict[str, Decimal] = {}
    for key, raw in mapping.items():
        if not raw:
            continue
        try:
            value = Decimal(raw)
        except Exception:  # noqa: BLE001
            continue
        if value > 0:
            out[key] = value
    return out


def fetch_live_frankfurter(
    *,
    transport_factory: Callable[[], Any] | None = None,
    get_json: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[dict[str, Decimal], str, str, str]:
    """
    Fetch USD/EUR/GBP → JPY via Frankfurter.

    Returns (rates, source_name, source_url, retrieved_at_iso) or raises ValueError.
    """
    if live_fx_disabled() and get_json is None:
        raise ValueError("live FX disabled")

    base = frankfurter_base_url().rstrip("?")
    # One request: USD base with JPY/EUR/GBP, then cross-convert to *_TO_JPY.
    url = f"{base}?from=USD&to=JPY,EUR,GBP"
    if get_json is not None:
        payload = get_json(url)
    else:
        payload = _http_get_json(url, transport_factory=transport_factory)

    if not isinstance(payload, dict):
        raise ValueError("malformed provider response")
    rates_raw = payload.get("rates")
    if not isinstance(rates_raw, dict):
        raise ValueError("malformed provider rates")
    try:
        jpy = Decimal(str(rates_raw["JPY"]))
        eur = Decimal(str(rates_raw["EUR"]))
        gbp = Decimal(str(rates_raw["GBP"]))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"missing required currencies: {exc}") from exc
    if jpy <= 0 or eur <= 0 or gbp <= 0:
        raise ValueError("non-positive provider rate")
    rates = {
        "USD_TO_JPY": jpy,
        "EUR_TO_JPY": jpy / eur,
        "GBP_TO_JPY": jpy / gbp,
    }
    date_raw = str(payload.get("date") or "").strip()
    # Freshness is based on when *we* retrieved the rate, not the ECB reference calendar day.
    retrieved_at = datetime.now(tz=UTC).isoformat()
    if date_raw:
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("malformed provider timestamp") from exc
    return rates, "Frankfurter", url, retrieved_at


def _http_get_json(
    url: str,
    *,
    transport_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    import httpx

    from config.transport import TransportSettings
    from utils.transport.transport import HttpTransport

    settings = TransportSettings(
        timeout_seconds=provider_timeout_seconds(),
        max_retries=provider_max_retries(),
        backoff_base_seconds=0.4,
        backoff_max_seconds=2.0,
    )
    if transport_factory is not None:
        transport = transport_factory()
        response = transport.get(url)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("malformed provider response")
        return payload

    transport = HttpTransport(marketplace_name="fx_frankfurter", settings=settings)
    last_error: Exception | None = None
    attempts = max(1, provider_max_retries() + 1)
    for attempt in range(attempts):
        try:
            response = transport.get(url)
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("malformed provider response")
            return payload
        except (httpx.TimeoutException, httpx.NetworkError, OSError) as exc:
            last_error = exc
            logger.warning("FX live fetch attempt %s failed: %s", attempt + 1, exc)
            continue
        except Exception as exc:  # noqa: BLE001
            # Permanent validation / parse errors — do not retry endlessly
            raise ValueError(str(exc) or type(exc).__name__) from exc
    raise ValueError(f"timeout or network error: {last_error}")


def acquire_session_fx_snapshot(
    session_id: str,
    *,
    transport_factory: Callable[[], Any] | None = None,
    get_json: Callable[[str], dict[str, Any]] | None = None,
    persist: bool = True,
) -> FxAcquireResult:
    """
    Priority: live → stored valid → explicit manual env → fail safely.

    Never silently uses DEFAULT_EXCHANGE_RATE (160).
    """
    sid = (session_id or "").strip() or "bulk-unknown"
    warnings: list[str] = []

    # 1) Live
    live_error = ""
    try:
        rates, source_name, source_url, retrieved_at = fetch_live_frankfurter(
            transport_factory=transport_factory,
            get_json=get_json,
        )
        valid, unavailable, err = validate_rates(rates)
        if err and not valid:
            raise ValueError(err)
        if persist:
            save_latest_rates(
                rates=valid,
                source_name=source_name,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        age = age_seconds_since(retrieved_at)
        freshness = classify_freshness(age)
        msg = "最新為替を取得しました。"
        if unavailable:
            warnings.append(
                f"{','.join(unavailable)}レートを取得できないため、該当通貨の商品を除外します。"
            )
            msg = (
                f"{unavailable[0]}レートを取得できないため、"
                f"{unavailable[0]}商品を除外しました。"
                if len(unavailable) == 1
                else msg + " " + warnings[-1]
            )
        snapshot = build_snapshot(
            session_id=sid,
            rates=valid,
            source_name=source_name,
            source_url=source_url,
            retrieved_at=retrieved_at,
            freshness_status=freshness,
            fallback_used=False,
            fallback_reason="",
            stored_rate_age_seconds=age,
            warnings=warnings,
            unavailable_currencies=unavailable,
            user_message=msg,
        )
        if persist:
            save_snapshot(snapshot)
        return FxAcquireResult(ok=True, snapshot=snapshot, user_message=msg)
    except Exception as exc:  # noqa: BLE001
        live_error = str(exc) or type(exc).__name__
        logger.info("Live FX unavailable: %s", live_error)

    # 2) Stored
    stored = load_latest_rates()
    if stored:
        rates_raw = stored.get("rates") or {}
        parsed: dict[str, Decimal] = {}
        if isinstance(rates_raw, dict):
            for key, value in rates_raw.items():
                try:
                    amount = Decimal(str(value))
                except Exception:  # noqa: BLE001
                    continue
                if amount > 0:
                    parsed[str(key)] = amount
        valid, unavailable, err = validate_rates(parsed)
        retrieved_at = str(stored.get("retrieved_at") or stored.get("saved_at") or "")
        age = age_seconds_since(retrieved_at)
        freshness = classify_freshness(age)
        if valid and freshness != FxFreshness.UNUSABLE.value and not err:
            if age is not None and age <= fresh_max_age_seconds():
                status = FxFreshness.FRESH.value
                msg = "最新為替を取得できなかったため、保存レートを使用しています。"
            elif age is not None and age <= stale_max_age_seconds():
                status = FxFreshness.STALE.value
                msg = "古い為替レートを使用しています。利益判断に注意してください。"
            else:
                status = freshness
                msg = "最新為替を取得できなかったため、保存レートを使用しています。"
            warn_list = [msg]
            if unavailable:
                warn_list.append(f"利用不可通貨: {', '.join(unavailable)}")
            snapshot = build_snapshot(
                session_id=sid,
                rates=valid,
                source_name=str(stored.get("source_name") or "stored_rates"),
                source_url=str(stored.get("source_url") or ""),
                retrieved_at=retrieved_at or datetime.now(tz=UTC).isoformat(),
                freshness_status=status,
                fallback_used=True,
                fallback_reason=f"live_failed:{live_error}",
                stored_rate_age_seconds=age,
                warnings=warn_list,
                unavailable_currencies=unavailable,
                user_message=msg,
            )
            if persist:
                save_snapshot(snapshot)
            return FxAcquireResult(ok=True, snapshot=snapshot, user_message=snapshot.user_message)

    # 3) Manual explicit env (not DEFAULT_EXCHANGE_RATE)
    manual = _manual_rates_from_env()
    valid, unavailable, err = validate_rates(manual)
    if valid and not err:
        msg = "手動設定レートを使用しています。"
        warnings = [msg]
        if unavailable:
            warnings.append(f"利用不可通貨: {', '.join(unavailable)}")
        snapshot = build_snapshot(
            session_id=sid,
            rates=valid,
            source_name="manual_env",
            source_url="",
            retrieved_at=datetime.now(tz=UTC).isoformat(),
            freshness_status=FxFreshness.MANUAL.value,
            fallback_used=True,
            fallback_reason=f"live_failed:{live_error};stored_unavailable",
            stored_rate_age_seconds=None,
            warnings=warnings,
            unavailable_currencies=unavailable,
            user_message=msg,
        )
        if persist:
            save_snapshot(snapshot)
        return FxAcquireResult(ok=True, snapshot=snapshot, user_message=msg)

    msg = "為替レートを取得できません。仕入れ上限付き一括取得を開始できません。"
    return FxAcquireResult(
        ok=False,
        snapshot=None,
        user_message=msg,
        failure_reason=live_error or "no trustworthy rate",
    )
