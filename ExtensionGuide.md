# BrandProfitFinder — Extension Guide

How to extend BrandProfitFinder without breaking Version 1 contracts.

---

## Overview

Extensions fall into three categories:

1. **Overseas scanners** — new sourcing stores (`scanner/`)
2. **Domestic marketplaces** — new sale-price sources (`marketplace/`)
3. **Pipeline hooks** — identity, ranking weights, comparison config

Do not modify public API signatures of existing classes when extending. Prefer subclassing and factory registration.

---

## Adding an Overseas Scanner

### 1. Implement the scanner

Create `scanner/<store>.py` extending `BaseScanner`:

```python
from scanner.base_scanner import BaseScanner
from models.product import Product

class ExampleScanner(BaseScanner):
    store_name = "example"

    def scan(self) -> list[Product]:
        # Parse local HTML/JSON fixture or configured source
        ...
```

### 2. Register in factory

Add the scanner to `scanner/scanner_factory.py`:

```python
SCANNERS = {
    "cettire": CettireScanner,
    "baltini": BaltiniScanner,
    "italist": ItalistScanner,
    "example": ExampleScanner,
}
```

### 3. Add fixtures and tests

- HTML/JSON fixture: `tests/fixtures/example_search_results.html`
- Unit tests: `tests/test_example.py`
- Factory test update: `tests/test_scanner_factory.py`

### Constraints

- No live site access in tests
- No Selenium/Playwright
- No CAPTCHA or access-limit bypass logic
- Do not hardcode real product data in Python source

---

## Adding a Domestic Marketplace

### Path A — Legacy BaseMarketplace (most marketplaces)

1. **Client** — `marketplace/<name>_client.py` with protocol + fake client for tests
2. **Parser** — `marketplace/<name>_response_parser.py` → `MarketplaceListing`
3. **Marketplace** — `marketplace/<name>_marketplace.py` extends `BaseMarketplace`
4. **Settings** — `marketplace/<name>_settings.py` from environment
5. **Factory** — register in `marketplace/marketplace_factory.py`
6. **Fixtures** — `tests/fixtures/<name>_*.json`
7. **Tests** — parser, client, integration, architecture safety
8. **main.py** — demo flag and `build_<name>_demo_client()`

Follow existing patterns in `yahoo_marketplace.py`, `stockx_marketplace.py`, or `goat_marketplace.py`.

### Path B — MarketplaceAdapter (recommended for new integrations)

For marketplaces that participate in cross-marketplace comparison with structured identity:

1. Extend `MarketplaceAdapter` instead of only `BaseMarketplace`
2. Override capability properties as needed:

```python
from marketplace.adapter import MarketplaceAdapter

class ExampleMarketplace(MarketplaceAdapter):
    marketplace_name = "example"

    @property
    def uses_fixture_data(self) -> bool:
        return True

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        ...
```

3. Comparison service auto-routes adapters through `MarketplaceSearchService`

### MarketplaceListing requirements

Populate fields used by identity and profit pipelines:

| Field | Used by |
|-------|---------|
| `listing_id`, `title` | Validation, display |
| `price_jpy` or currency + amount | Profit calculation |
| `jan_code`, `model_number`, `style_code` | Identity matching |
| `metadata` | Intelligence, warnings |

Unknown shipping, fees, or currency conversion must remain `None` — never default to zero.

---

## Profit Policy Configuration

Add marketplace-specific economics in `price_compare/profit_config.py`:

```python
from profit_policy import FeePolicy, ShippingPolicy, TaxPolicy, MarketplaceConfiguration

EXAMPLE_CONFIG = MarketplaceConfiguration(
    marketplace_id="example",
    fee_policy=FeePolicy(fee_rate=Decimal("0.095")),
    shipping_policy=ShippingPolicy(...),
    tax_policy=TaxPolicy(...),
)
```

Register in `marketplace_configurations()` and `resolve_marketplace()`.

`ProfitCalculator` consumes configurations automatically — do not duplicate fee math in marketplace classes.

---

## Import Cost Extensions

Optional ancillary costs pass through `ImportCostContext`:

```python
from import_cost import ImportCostContext, ImportCostEngine

context = ImportCostContext.create(
    source_purchase=Decimal("100"),
    currency="USD",
    exchange_rate=Decimal("150"),
    domestic_sale_jpy=Decimal("25000"),
    payment_fee_jpy=Decimal("200"),
)
breakdown = ImportCostEngine().calculate(context, marketplace_config)
```

Omitting optional fields preserves legacy numeric parity.

---

## Ranking Weight Customization

Adjust weights in `RankingPolicy` or via `profit_config` ranking fields:

```python
from ranking_foundation import RankingPolicy

policy = RankingPolicy.default().with_weights(
    profit_margin_weight=Decimal("0.3"),
    roi_weight=Decimal("0.2"),
)
```

Comparison ranking consumes enriched metadata; changing weights affects `ranking_foundation_score` but not the legacy lexicographic sort keys unless metadata keys change.

---

## Comparison Configuration

```python
from comparison.config import ComparisonConfig

config = ComparisonConfig(
    min_match_score=Decimal("30"),
    require_identity_match=True,
    expected_marketplaces=["stockx", "goat"],
)
```

Use with `CrossMarketplaceComparisonService(config=config)`.

---

## Excel Export Extensions

1. Add column names to `excel/template.py` (`MARKETPLACE_COMPARISON_COLUMNS` or profit columns)
2. Map values in `excel/formatter.py` or `comparison/formatter.py`
3. Update `scripts/validate_workbook_phase24.py` if row/column counts change
4. Add export tests in `tests/test_excel_*.py`

Identity fields should use `product_identity/formatter.identity_result_to_export_fields()` for consistent keys.

---

## Product Identity Extensions

To add a new identifier field:

1. Extend extraction in `product_identity/extractor.py`
2. Add evidence rules in `product_identity/evidence.py`
3. Update policy in `product_identity/policy.py` if decision logic changes
4. Add tests in `tests/test_product_identity_*.py`

Never use identity decisions as authenticity guarantees in user-facing text.

---

## Environment Variables

Add new settings to:

1. `config/settings.py`
2. `.env.example`
3. Marketplace-specific settings module

Document demo flags in this guide and `README.md`.

---

## Checklist for New Marketplace

- [ ] `BaseMarketplace` or `MarketplaceAdapter` implementation
- [ ] Parser with fixture tests
- [ ] Fake client for demo mode
- [ ] Factory registration
- [ ] `profit_config` marketplace configuration
- [ ] Architecture safety test
- [ ] main.py demo flag
- [ ] `.env.example` entries
- [ ] No network access in default test run

---

## Related Documentation

- [Architecture.md](Architecture.md) — pipeline and dependency diagrams
- [DeveloperGuide.md](DeveloperGuide.md) — setup and testing
- [ReleaseChecklist.md](ReleaseChecklist.md) — verification before release
