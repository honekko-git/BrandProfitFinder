"""Brand catalog for tier-based and opportunity-based discovery targeting."""

from __future__ import annotations

from profit_discovery.brand_catalog.models import (
    BrandCapitalLevel,
    BrandOpportunityProfile,
    BrandProfile,
    BrandTier,
)

HIGH_DEMAND_THRESHOLD = 80.0

DEFAULT_OPPORTUNITY_PROFILES: tuple[BrandOpportunityProfile, ...] = (
    BrandOpportunityProfile(
        name="Chanel",
        profit_score=95.0,
        demand_score=92.0,
        turnover_score=85.0,
        risk_score=15.0,
        capital_level=BrandCapitalLevel.HIGH.value,
    ),
    BrandOpportunityProfile(
        name="Louis Vuitton",
        profit_score=93.0,
        demand_score=90.0,
        turnover_score=84.0,
        risk_score=18.0,
        capital_level=BrandCapitalLevel.HIGH.value,
    ),
    BrandOpportunityProfile(
        name="Miu Miu",
        profit_score=88.0,
        demand_score=86.0,
        turnover_score=82.0,
        risk_score=22.0,
        capital_level=BrandCapitalLevel.HIGH.value,
    ),
    BrandOpportunityProfile(
        name="Hermes",
        profit_score=94.0,
        demand_score=88.0,
        turnover_score=80.0,
        risk_score=20.0,
        capital_level=BrandCapitalLevel.HIGH.value,
    ),
    BrandOpportunityProfile(
        name="Coach",
        profit_score=85.0,
        demand_score=88.0,
        turnover_score=90.0,
        risk_score=25.0,
        capital_level=BrandCapitalLevel.HIGH.value,
    ),
    BrandOpportunityProfile(
        name="Dior",
        profit_score=82.0,
        demand_score=80.0,
        turnover_score=78.0,
        risk_score=28.0,
        capital_level=BrandCapitalLevel.A.value,
    ),
    BrandOpportunityProfile(
        name="Celine",
        profit_score=80.0,
        demand_score=78.0,
        turnover_score=76.0,
        risk_score=30.0,
        capital_level=BrandCapitalLevel.A.value,
    ),
    BrandOpportunityProfile(
        name="Loewe",
        profit_score=78.0,
        demand_score=76.0,
        turnover_score=74.0,
        risk_score=32.0,
        capital_level=BrandCapitalLevel.A.value,
    ),
    BrandOpportunityProfile(
        name="Bottega Veneta",
        profit_score=79.0,
        demand_score=77.0,
        turnover_score=75.0,
        risk_score=31.0,
        capital_level=BrandCapitalLevel.A.value,
    ),
    BrandOpportunityProfile(
        name="Prada",
        profit_score=81.0,
        demand_score=79.0,
        turnover_score=77.0,
        risk_score=29.0,
        capital_level=BrandCapitalLevel.A.value,
    ),
    BrandOpportunityProfile(
        name="Gucci",
        profit_score=75.0,
        demand_score=74.0,
        turnover_score=72.0,
        risk_score=35.0,
        capital_level=BrandCapitalLevel.B.value,
    ),
    BrandOpportunityProfile(
        name="Fendi",
        profit_score=73.0,
        demand_score=72.0,
        turnover_score=70.0,
        risk_score=36.0,
        capital_level=BrandCapitalLevel.B.value,
    ),
    BrandOpportunityProfile(
        name="Balenciaga",
        profit_score=72.0,
        demand_score=70.0,
        turnover_score=68.0,
        risk_score=38.0,
        capital_level=BrandCapitalLevel.B.value,
    ),
    BrandOpportunityProfile(
        name="Saint Laurent",
        profit_score=74.0,
        demand_score=73.0,
        turnover_score=71.0,
        risk_score=37.0,
        capital_level=BrandCapitalLevel.B.value,
    ),
    BrandOpportunityProfile(
        name="Burberry",
        profit_score=71.0,
        demand_score=69.0,
        turnover_score=67.0,
        risk_score=40.0,
        capital_level=BrandCapitalLevel.B.value,
    ),
)

_CAPITAL_TO_TIER = {
    BrandCapitalLevel.HIGH.value: BrandTier.S.value,
    BrandCapitalLevel.A.value: BrandTier.A.value,
    BrandCapitalLevel.B.value: BrandTier.B.value,
}


def _to_brand_profile(profile: BrandOpportunityProfile) -> BrandProfile:
    return BrandProfile(
        name=profile.name,
        tier=_CAPITAL_TO_TIER.get(profile.capital_level.upper(), profile.capital_level),
        enabled=profile.enabled,
    )


def _to_opportunity_profile(brand: BrandProfile) -> BrandOpportunityProfile:
    capital_level = {
        BrandTier.S.value: BrandCapitalLevel.HIGH.value,
        BrandTier.A.value: BrandCapitalLevel.A.value,
        BrandTier.B.value: BrandCapitalLevel.B.value,
    }.get(brand.tier.upper(), brand.tier)
    return BrandOpportunityProfile(
        name=brand.name,
        profit_score=70.0,
        demand_score=70.0,
        turnover_score=70.0,
        risk_score=30.0,
        capital_level=capital_level,
        enabled=brand.enabled,
    )


DEFAULT_BRAND_PROFILES: tuple[BrandProfile, ...] = tuple(
    _to_brand_profile(profile) for profile in DEFAULT_OPPORTUNITY_PROFILES
)


class BrandCatalog:
    """Manage discoverable brands grouped by tier and opportunity score."""

    def __init__(
        self,
        brands: list[BrandProfile] | None = None,
        opportunity_profiles: list[BrandOpportunityProfile] | None = None,
    ) -> None:
        if opportunity_profiles is not None:
            self._opportunity_profiles = list(opportunity_profiles)
            self._brands = [_to_brand_profile(profile) for profile in self._opportunity_profiles]
        else:
            self._brands = list(brands or DEFAULT_BRAND_PROFILES)
            self._opportunity_profiles = [_to_opportunity_profile(profile) for profile in self._brands]

    @classmethod
    def default(cls) -> BrandCatalog:
        """Return the default seeded brand catalog."""
        return cls(opportunity_profiles=list(DEFAULT_OPPORTUNITY_PROFILES))

    def get_all_brands(self) -> tuple[BrandProfile, ...]:
        """Return all catalog brands."""
        return tuple(self._brands)

    def get_all_opportunity_profiles(self) -> tuple[BrandOpportunityProfile, ...]:
        """Return all opportunity profiles in the catalog."""
        return tuple(self._opportunity_profiles)

    def get_by_tier(self, tier: str) -> tuple[BrandProfile, ...]:
        """Return brands that match the requested tier."""
        normalized = tier.strip().upper()
        return tuple(brand for brand in self._brands if brand.tier.upper() == normalized)

    def get_by_opportunity_score(self) -> tuple[BrandOpportunityProfile, ...]:
        """Return enabled brands sorted by opportunity score descending."""
        enabled = [profile for profile in self._opportunity_profiles if profile.enabled]
        return tuple(sorted(enabled, key=lambda profile: profile.calculate_opportunity_score(), reverse=True))

    def get_high_demand_brands(self, *, threshold: float = HIGH_DEMAND_THRESHOLD) -> tuple[BrandOpportunityProfile, ...]:
        """Return enabled brands with demand score at or above the threshold."""
        return tuple(
            profile
            for profile in self._opportunity_profiles
            if profile.enabled and profile.demand_score >= threshold
        )

    def get_enabled_brands(self) -> tuple[BrandProfile, ...]:
        """Return enabled catalog brands."""
        return tuple(brand for brand in self._brands if brand.enabled)

    def get_enabled_opportunity_profiles(self) -> tuple[BrandOpportunityProfile, ...]:
        """Return enabled opportunity profiles."""
        return tuple(profile for profile in self._opportunity_profiles if profile.enabled)

    def add_brand(self, brand: BrandProfile) -> None:
        """Append one brand profile to the catalog."""
        self._brands.append(brand)
        self._opportunity_profiles.append(_to_opportunity_profile(brand))

    def add_opportunity_profile(self, profile: BrandOpportunityProfile) -> None:
        """Append one opportunity profile to the catalog."""
        self._opportunity_profiles.append(profile)
        self._brands.append(_to_brand_profile(profile))

    def brand_names_for_tier(self, tier: str) -> list[str]:
        """Return enabled brand names for one tier."""
        return [brand.name for brand in self.get_by_tier(tier) if brand.enabled]
