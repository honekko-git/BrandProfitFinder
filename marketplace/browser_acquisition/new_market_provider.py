"""New-market price provider interface (BUYMA / Rakuten / Amazon later).

No fragile scrapers in V1.0. Mock provider supports tests and verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from marketplace.browser_acquisition.new_market_price import (
    NewMarketEvidence,
    NewMarketValidationResult,
    validate_new_market_price,
)
from marketplace.browser_acquisition.product_identity import ProductIdentity


class NewMarketPriceProvider(Protocol):
    """Adapter interface for new-product price sources."""

    def get_prices(self, product_identity: ProductIdentity) -> list[NewMarketEvidence]:
        """Return candidate new-market prices for the product identity."""


@dataclass
class NullNewMarketPriceProvider:
    """Default provider: no new-market data (no warning, no ranking impact)."""

    def get_prices(self, product_identity: ProductIdentity) -> list[NewMarketEvidence]:
        return []


@dataclass
class MockNewMarketPriceProvider:
    """In-memory catalog for tests and offline verification.

    Architecture allows later BUYMA / Rakuten / Amazon providers with the same interface.
    """

    catalog: list[NewMarketEvidence] = field(default_factory=list)

    def get_prices(self, product_identity: ProductIdentity) -> list[NewMarketEvidence]:
        # Provider returns catalog; identity match filtering happens in validate_new_market_price.
        # Optionally narrow by brand token to avoid huge catalogs later.
        brand = (product_identity.brand or "").strip().lower()
        if not brand:
            return list(self.catalog)
        out: list[NewMarketEvidence] = []
        for item in self.catalog:
            if brand in (item.title or "").lower() or brand.upper() in (item.title or "").upper():
                out.append(item)
        return out


def resolve_new_market_validation(
    *,
    product_identity: ProductIdentity,
    used_predicted_price_jpy,
    provider: NewMarketPriceProvider | None = None,
    injected_candidates: list[NewMarketEvidence] | None = None,
) -> NewMarketValidationResult:
    """Run provider + validation. Injected candidates override provider results when set."""
    active = provider or NullNewMarketPriceProvider()
    if injected_candidates is not None:
        candidates = list(injected_candidates)
    else:
        candidates = list(active.get_prices(product_identity) or [])
    return validate_new_market_price(
        identity=product_identity,
        used_predicted_price_jpy=used_predicted_price_jpy,
        candidates=candidates,
    )


def demo_buyma_spr26z_catalog() -> list[NewMarketEvidence]:
    """Known verification fixture — not live scraped."""
    now = datetime.now(tz=UTC).isoformat()
    return [
        NewMarketEvidence(
            marketplace="BUYMA",
            title="PRADA SPR26Z Sunglasses Pink",
            price=42800,
            currency="JPY",
            url="https://www.buyma.com/example/spr26z",
            retrieved_at=now,
            availability="in_stock",
            condition="NEW",
        ),
        NewMarketEvidence(
            marketplace="BUYMA",
            title="PRADA Sunglasses Acetate Black",
            price=98000,
            currency="JPY",
            url="https://www.buyma.com/example/prada-sunglasses",
            retrieved_at=now,
            availability="in_stock",
            condition="NEW",
        ),
    ]
