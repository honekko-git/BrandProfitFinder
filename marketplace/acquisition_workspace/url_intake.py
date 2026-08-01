"""Public URL manual intake."""

from __future__ import annotations

from decimal import Decimal

from marketplace.acquisition_workspace.models import ParsedCandidate, SourceType


def intake_public_url(
    *,
    url: str,
    title: str,
    price: Decimal,
    currency: str,
    source_name: str = "Public URL",
    condition: str = "",
) -> ParsedCandidate:
    """Create one candidate from manual public URL intake."""
    return ParsedCandidate(
        title=title.strip(),
        brand="",
        category="Wallet",
        condition=condition.strip(),
        purchase_price=price,
        currency=currency.strip().upper(),
        purchase_url=url.strip(),
        source_name=source_name,
        external_id="",
        image_url="",
        raw_description="",
        parser_strategy=SourceType.PUBLIC_URL.value,
    )
