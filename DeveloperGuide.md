# BrandProfitFinder — Developer Guide

Guide for contributors working on Version 1.0.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ (project tested on 3.14) |
| Git | Any recent version |
| OS | Windows, macOS, or Linux |

---

## Repository Layout

```
BrandProfitFinder/
├── config/              # Settings, constants, logging
├── models/              # Domain dataclasses
├── scanner/             # Overseas store parsers
├── marketplace/         # Domestic marketplace integrations
├── marketplace_search/  # Search request/result framework
├── product_identity/    # Identity evaluation
├── profit_policy/       # Marketplace fee/shipping/tax policies
├── import_cost/         # Import cost engine
├── price_compare/       # Profit calculator and ranking
├── profit_intelligence/ # Optional advisory scoring
├── ranking_foundation/  # Weighted ranking signals
├── comparison/          # Cross-marketplace comparison
├── excel/               # Workbook export
├── used_luxury/         # Used-item enrichment models
├── utils/               # HTTP, parsing, exchange rate helpers
├── tests/               # Pytest suite and fixtures
├── scripts/             # Generators and validators
├── docs/                # Legacy phase specifications
├── output/              # Generated Excel (gitignored)
├── logs/                # Runtime logs (gitignored)
├── main.py              # CLI entry point
├── Architecture.md      # System architecture
├── ExtensionGuide.md    # Adding integrations
└── ReleaseChecklist.md  # Release verification
```

---

## Environment Setup

1. Clone the repository and enter the project directory.

2. Create a virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. Install dependencies (do not modify `requirements.txt` without review):

```bash
pip install -r requirements.txt
```

4. Copy environment template:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # macOS/Linux
```

Default `main.py` execution uses local fixtures and performs **no network access**. Live API keys are optional.

---

## Running the Application

### Default local pipeline

```bash
python main.py
```

Exports `output/profit_ranking.xlsx` using the local marketplace fixture.

### Identity demo

```bash
python main.py --identity-demo
```

Runs synthetic identity evaluation cases (no Excel export).

### Cross-marketplace comparison demo

```bash
python main.py --comparison-demo
python main.py --comparison-demo --profit-intelligence
```

Uses StockX + GOAT fixtures. Appends Marketplace Comparison sheet.

### Single marketplace demos

```bash
python main.py --demo-stockx
python main.py --demo-goat
python main.py --demo-farfetch
python main.py --demo-vestiaire
```

See `main.py` `build_cli_parser()` for the full flag list.

---

## Testing Strategy

### Full suite

```bash
python -m pytest -q
```

Expected: **1370+ tests**, all passing, no network access.

### Focused regression (Phases 20–25)

```bash
python -m pytest tests/test_product_identity_phase20.py \
                 tests/test_profit_policy_phase21.py \
                 tests/test_marketplace_search_phase22.py \
                 tests/test_import_cost_phase23.py \
                 tests/test_ranking_foundation_phase24.py \
                 tests/test_comparison_unification_phase25.py -q
```

### Workbook validation

Run comparison demo first, then:

```bash
python scripts/validate_workbook_phase24.py
```

Expect: `workbook OK: 31 columns, 3 rows, 8 identity columns`

### Test organization

| Pattern | Purpose |
|---------|---------|
| `tests/test_<module>.py` | Unit tests per module |
| `tests/test_<marketplace>_*.py` | Marketplace integration |
| `tests/test_*_phase*.py` | Phase regression suites |
| `tests/test_*_architecture_safety.py` | Import boundary guards |
| `tests/fixtures/` | JSON, HTML, and synthetic payloads |

### Conventions

- No live HTTP in tests — patch `utils.http` or inject fake clients
- Use deterministic fixtures under `tests/fixtures/`
- Prefer explicit assertions over snapshot files
- Architecture safety tests enforce module boundary rules

---

## Key Public APIs

### Product identity

```python
from product_identity import ProductIdentityService, IdentityDecision

service = ProductIdentityService()
result = service.evaluate_product_listing(product, listing)
print(result.decision, result.confidence)
```

### Profit calculation

```python
from decimal import Decimal
from price_compare.profit_calculator import ProfitCalculator

calculator = ProfitCalculator()
result = calculator.calculate(product, Decimal("50000"), "stockx")
print(result.profit_jpy, result.profit_margin)
```

### Cross-marketplace comparison

```python
from comparison import CrossMarketplaceComparisonService
from comparison.config import ComparisonConfig

service = CrossMarketplaceComparisonService(config=ComparisonConfig())
run = service.compare_products(products, marketplaces, calculator)
for comparison in run.products:
    print(comparison.selected_review_marketplace, comparison.comparable_count)
```

### Marketplace search (adapter path)

```python
from marketplace_search import SearchRequest, MarketplaceSearchService

request = SearchRequest.from_product(product, "stockx")
result = MarketplaceSearchService().search(stockx_adapter, request)
print(result.status, len(result.valid_listings))
```

### Data truth and discovery transparency

Version 2 workspace and batch-profit outputs expose two reusable transparency objects on acquisition candidates:

- `DataTruthSummary`
- `DiscoveryMetadata`

Use them to explain where values came from and how trustworthy they are without changing pipeline logic.

#### Runtime labels

- `LIVE` — comparable or market data came from a live request or live cache
- `FIXTURE` — comparable or market data came from deterministic fixture input
- `IMPORT` — purchase-side candidate data came from CSV, manual entry, saved HTML, public URL, or existing imported rows

#### Acquisition modes

- `MANUAL` — user-entered listing fields
- `CSV` — uploaded structured import
- `SAVED_HTML` — parsed saved browser HTML
- `PUBLIC_URL` — manually supplied public listing URL
- `EXISTING_IMPORT` — copied from persisted imported listings

#### Estimated fields

- `used_estimated_price=True` means the selling-side estimate was inferred from comparable results
- `used_estimated_shipping=True` means shipping cost is not live-carrier quoted and remains a modeled estimate
- `fee_source="Configured"` means cost profile configuration provided the fee inputs

#### Confidence

- `HIGH` — live comparable evidence with enough accepted results for a stable estimate
- `MEDIUM` — some evidence exists, but the estimate is still partly inferred
- `LOW` — weak or missing comparable evidence

#### Developer expectations

- `confidence_level` must never be blank
- `runtime_mode` must always be populated
- `query_count >= 1`
- `candidate_count >= comparable_count`

CLI, browser workspace pages, and acquisition exports should all read from the same candidate transparency metadata rather than synthesizing their own labels.

### Used Listing Ranking MVP

Purpose: give operators a practical ordered view of acquisition candidates so they can compare profit, ROI, demand proxies, and confidence, then open the original overseas listing and decide manually.

#### Components and fixed weights

| Component | Weight | Source |
|-----------|--------|--------|
| Profit | 35% | `last_net_profit` falling back to `last_gross_profit` |
| ROI | 30% | profit / `purchase_price_jpy` as percent |
| Demand | 20% | `discovery_metadata.comparable_count` as sold-sample proxy |
| Confidence | 15% | `DataTruthSummary.confidence_level` mapped HIGH=100, MEDIUM=60, LOW=25 |

Overall score = weighted sum of 0–100 component scores, rounded to one decimal. Normalization is min-max within the current eligible set. Negative profit and zero/negative ROI score 0. Missing sales count scores 0.

#### Mandatory source listing URL

Ranking eligibility requires a non-empty `http://` or `https://` value in the existing `purchase_url` field. Candidates without a valid URL stay visible in the workspace with a warning, but are excluded from ranked results. There is no URL-less purchasable candidate concept.

#### Short analysis

`analysis_summary` is a deterministic two-to-four sentence text built from scores and warnings. It never says “buy this” or issues a final decision. The human user must inspect the original listing and make the sourcing decision.

#### Intentionally deferred

Adaptive/custom weights, ML, advanced condition/liquidity/price-stability scoring, forecasting, and automatic purchasing/payment/negotiation are deferred until after real prototype usage feedback.

---

## Module Docstring Standards

Public packages export through `__init__.py` with `__all__`. Each package should have:

1. One-line module summary in `__init__.py` or primary module
2. Class docstrings describing responsibility
3. Method docstrings for non-obvious behavior
4. Type hints on all public functions

Frozen dataclasses (`frozen=True, slots=True`) are used for policy and context objects.

---

## Logging

Configured in `config/logging_config.py`. Runtime logs write to `logs/brand_profit_finder.log`.

```python
import logging
logger = logging.getLogger(__name__)
```

---

## Coding Standards

See `docs/09_CODING_STANDARD.md` for legacy project conventions. Version 1 additions:

- Keep business logic out of `config/` and `models/`
- Use `profit_policy/money.round_jpy()` for JPY rounding
- Use `product_identity/util.stable_unique()` or `comparison/util.stable_unique()` for warning deduplication
- Do not treat unknown costs or currencies as zero
- Preserve backward-compatible sort orders in comparison ranking

---

## Common Development Tasks

### Add a test fixture

Place JSON/HTML under `tests/fixtures/`. Reference from tests with `Path(__file__).parent / "fixtures" / "..."`.

### Debug comparison pipeline

Enable INFO logging and run:

```bash
python main.py --comparison-demo
```

Inspect `comparison.service` log lines for product/marketplace counts.

### Verify identity decisions

```bash
python main.py --identity-demo
```

Summary line reports match/review/no_match/insufficient counts.

---

## Related Documentation

- [Architecture.md](Architecture.md) — diagrams and pipeline detail
- [ExtensionGuide.md](ExtensionGuide.md) — adding marketplaces
- [ReleaseChecklist.md](ReleaseChecklist.md) — pre-release verification
