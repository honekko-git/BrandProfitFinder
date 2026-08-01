"""Cost profiles for batch net profit estimation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

from models.price_result import PriceResult
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate

NOT_CONFIGURED = "Not configured"


@dataclass
class CostProfile:
    """Configurable cost assumptions for net profit display."""

    profile_name: str
    exchange_rate: float | None = None
    international_shipping_jpy: Decimal | None = None
    forwarding_fee_jpy: Decimal | None = None
    import_duty_rate: Decimal | None = None
    import_tax_rate: Decimal | None = None
    payment_fee_rate: Decimal | None = None
    domestic_platform_fee_rate: Decimal | None = None
    domestic_shipping_jpy: Decimal | None = None
    inspection_or_repair_reserve_jpy: Decimal | None = None
    miscellaneous_cost_jpy: Decimal | None = None
    assumption_note: str = ""

    def configured_fields(self) -> list[str]:
        fields = [
            "international_shipping_jpy",
            "forwarding_fee_jpy",
            "import_duty_rate",
            "import_tax_rate",
            "payment_fee_rate",
            "domestic_platform_fee_rate",
            "domestic_shipping_jpy",
            "inspection_or_repair_reserve_jpy",
            "miscellaneous_cost_jpy",
        ]
        return [name for name in fields if getattr(self, name) is None]

    def is_net_complete(self) -> bool:
        return len(self.configured_fields()) == 0

    def active_exchange_rate(self) -> float:
        if self.exchange_rate is not None:
            return self.exchange_rate
        return resolve_usd_jpy_exchange_rate()


@dataclass
class CostProfileStore:
    """In-memory and file-backed cost profile store."""

    profiles: dict[str, CostProfile] = field(default_factory=dict)
    storage_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.profiles:
            self.profiles = default_cost_profiles()
        if self.storage_path and self.storage_path.exists():
            self._load()

    def get(self, name: str) -> CostProfile:
        key = name.strip().lower()
        if key in self.profiles:
            return self.profiles[key]
        if key == "custom" and "custom" in self.profiles:
            return self.profiles["custom"]
        return self.profiles["standard"]

    def save_profile(self, profile: CostProfile) -> None:
        self.profiles[profile.profile_name.strip().lower()] = profile
        if self.storage_path:
            self._persist()

    def _load(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        for item in payload.get("profiles", []):
            profile = _profile_from_dict(item)
            self.profiles[profile.profile_name.lower()] = profile

    def _persist(self) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"profiles": [_profile_to_dict(profile) for profile in self.profiles.values()]}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_cost_profiles() -> dict[str, CostProfile]:
    """Return default cost profiles without pretending unconfigured values are zero."""
    return {
        "conservative": CostProfile(
            profile_name="Conservative",
            assumption_note="Placeholder profile. Values are assumptions until configured.",
            international_shipping_jpy=Decimal("4500"),
            forwarding_fee_jpy=Decimal("1500"),
            import_duty_rate=Decimal("0.10"),
            import_tax_rate=Decimal("0.10"),
            payment_fee_rate=Decimal("0.03"),
            domestic_platform_fee_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("800"),
            inspection_or_repair_reserve_jpy=Decimal("5000"),
            miscellaneous_cost_jpy=Decimal("2000"),
        ),
        "standard": CostProfile(
            profile_name="Standard",
            assumption_note="Most cost fields are not configured. Net profit remains provisional.",
        ),
        "custom": CostProfile(
            profile_name="Custom",
            assumption_note="User-editable profile.",
        ),
    }


def compute_estimated_costs(
    *,
    profile: CostProfile,
    purchase_price_jpy: Decimal,
    selling_price_jpy: Decimal,
    gross_profit_result: PriceResult,
) -> tuple[Decimal | None, "EstimatedCosts"]:
    """Compute net profit using CostProfile without modifying ProfitCalculator."""
    from profit_discovery.discovery_validation.batch_profit.models import EstimatedCosts

    unconfigured = profile.configured_fields()
    exchange_display = f"{profile.active_exchange_rate():g} JPY/USD"

    def _value(name: str, amount: Decimal | None) -> Decimal:
        return amount if amount is not None else Decimal("0")

    intl_shipping = profile.international_shipping_jpy
    forwarding = profile.forwarding_fee_jpy
    duty_rate = profile.import_duty_rate
    tax_rate = profile.import_tax_rate
    payment_rate = profile.payment_fee_rate
    platform_rate = profile.domestic_platform_fee_rate
    domestic_ship = profile.domestic_shipping_jpy
    inspection = profile.inspection_or_repair_reserve_jpy
    misc = profile.miscellaneous_cost_jpy

    import_duty = purchase_price_jpy * duty_rate if duty_rate is not None else Decimal("0")
    import_tax = (purchase_price_jpy + import_duty) * tax_rate if tax_rate is not None else Decimal("0")
    payment_fee = purchase_price_jpy * payment_rate if payment_rate is not None else Decimal("0")
    platform_fee = selling_price_jpy * platform_rate if platform_rate is not None else Decimal("0")

    additional = (
        _value("international_shipping_jpy", intl_shipping)
        + _value("forwarding_fee_jpy", forwarding)
        + import_duty
        + import_tax
        + payment_fee
        + platform_fee
        + _value("domestic_shipping_jpy", domestic_ship)
        + _value("inspection_or_repair_reserve_jpy", inspection)
        + _value("miscellaneous_cost_jpy", misc)
    )

    costs = EstimatedCosts(
        exchange_rate=exchange_display,
        international_shipping_jpy=intl_shipping or Decimal("0"),
        forwarding_fee_jpy=forwarding or Decimal("0"),
        import_duty_jpy=import_duty,
        import_tax_jpy=import_tax,
        payment_fee_jpy=payment_fee,
        domestic_platform_fee_jpy=platform_fee,
        domestic_shipping_jpy=domestic_ship or Decimal("0"),
        inspection_or_repair_reserve_jpy=inspection or Decimal("0"),
        miscellaneous_cost_jpy=misc or Decimal("0"),
        total_additional_costs_jpy=additional,
        net_profit_complete=profile.is_net_complete(),
        unconfigured_fields=tuple(unconfigured),
    )

    if not profile.is_net_complete():
        return None, costs

    net_profit = gross_profit_result.profit_jpy - additional
    return net_profit, costs


def _profile_to_dict(profile: CostProfile) -> dict:
    data = asdict(profile)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = str(value)
    return data


def _profile_from_dict(data: dict) -> CostProfile:
    parsed = dict(data)
    for key in (
        "international_shipping_jpy",
        "forwarding_fee_jpy",
        "import_duty_rate",
        "import_tax_rate",
        "payment_fee_rate",
        "domestic_platform_fee_rate",
        "domestic_shipping_jpy",
        "inspection_or_repair_reserve_jpy",
        "miscellaneous_cost_jpy",
    ):
        if parsed.get(key) is not None:
            parsed[key] = Decimal(str(parsed[key]))
    return CostProfile(**parsed)
