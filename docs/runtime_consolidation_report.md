# Runtime Consolidation Report

**Phase:** V2-12A-1 — Version Control Consolidation & Safety Check  
**Branch:** `develop/v2`  
**Date:** 2026-07-29  
**Status:** Verification complete — no logic changes applied

---

## Current Architecture

```
python main.py discovery
        │
        ▼
BrandCatalog / CategoryCatalog
  (--brands, --tier, --category-priority)
        │
        ▼
MultiBrandDiscoveryRunner
  → DiscoveryRunner (supplier + domestic market connector)
  → ranked_candidates
  → ranked_opportunities (legacy OpportunityScorer)
        │
        ▼
build_production_discovery_pipeline()
  1. ProductIdentityResolver
  2. DuplicateResolver.merge_candidates()
  3. DemandQueryResolver + DemandLookup
  4. DemandIntegratedOpportunityScorer
  5. rank_demand_integrated_opportunities()
        │
        ▼
ranked_demand_opportunities
        │
        ├─► Console: Discovery Summary, TOP BUY, Demand Ranking, Showcase
        └─► Excel: Profit Analysis, Opportunity Ranking,
                   Demand Opportunity Ranking, Showcase
```

**Runtime mode (default):** Fixture-backed supplier and domestic market clients.  
**Entry point:** `main.py` dispatches `discovery` subcommand to `profit_discovery.cli.discovery_command.run_discovery_cli`.

---

## Package List

| Package | Path | `__init__.py` | Primary exports |
|---------|------|---------------|-----------------|
| profit_discovery | `profit_discovery/` | Yes | BuyDecisionEngine, BuyDecision, MaxPayCalculator |
| profit_discovery.cli | `profit_discovery/cli/` | Yes | run_discovery_command, build_production_discovery_pipeline |
| profit_discovery.showcase | `profit_discovery/showcase/` | Yes | ShowcaseFormatter, ShowcaseOpportunity |
| profit_discovery.multi_brand | `profit_discovery/multi_brand/` | Yes | MultiBrandDiscoveryRunner, MultiBrandDiscoveryResult |
| profit_discovery.opportunity | `profit_discovery/opportunity/` | Yes | OpportunityScorer, DemandIntegratedOpportunityScorer, pipelines |
| profit_discovery.discovery_runner | `profit_discovery/discovery_runner/` | Yes | DiscoveryRunner, DiscoveryCandidateResult |
| profit_discovery.market_connector | `profit_discovery/market_connector/` | Yes | SupplierMarketConnector |
| profit_discovery.brand_catalog | `profit_discovery/brand_catalog/` | Yes | BrandCatalog, BrandProfile |
| profit_discovery.category_catalog | `profit_discovery/category_catalog/` | Yes | CategoryCatalog, BrandCategoryResolver |
| profit_intelligence | `profit_intelligence/` | Yes | ProfitIntelligenceService |
| profit_intelligence.demand | `profit_intelligence/demand/` | Yes | DemandAnalyzer, DemandLookup, DemandQueryResolver |
| product_identity | `product_identity/` | Yes | ProductIdentityService, ProductIdentityEvaluator |
| product_identity (V2) | `product_identity/identity_resolver.py` | — | ProductIdentityResolver (module-level) |
| product_identity (V2) | `product_identity/duplicate_resolver.py` | — | DuplicateResolver (module-level) |
| supplier | `supplier/` | Yes | SupplierClient, SupplierProduct, create_supplier_client |
| supplier.config | `supplier/config.py` | — | SupplierRuntimeConfig (fixture/live) |
| supplier.factory | `supplier/factory.py` | — | resolve_supplier_client |
| marketplace | `marketplace/` | Yes (minimal) | Package root only |
| marketplace.domestic_market | `marketplace/domestic_market/` | Yes | DomesticMarketAggregator, clients |
| marketplace.yahoo_auction | `marketplace/yahoo_auction/` | Yes | Yahoo auction adapter layer |

**Note:** Showcase lives under `profit_discovery/showcase/`, not a top-level `showcase/` package.

### Import validation (2026-07-29)

All 19 target modules imported successfully:

- profit_discovery (+ cli, showcase, multi_brand, opportunity, discovery_runner, market_connector, brand_catalog, category_catalog)
- profit_intelligence (+ demand)
- product_identity (+ identity_resolver, duplicate_resolver)
- supplier (+ config, factory)
- marketplace.domestic_market, marketplace.yahoo_auction

---

## Runtime Flow

### CLI invocation

```bash
python main.py discovery --brands Chanel --keyword wallet
```

### Verified console sections

| Section | Status |
|---------|--------|
| Discovery Summary | Present |
| TOP BUY Candidates | Present |
| Demand Opportunity Ranking | Present |
| AI PROFIT DISCOVERY SHOWCASE | Present |

### Verified Excel sheets (export)

| Sheet | Status |
|-------|--------|
| Profit Analysis | Present |
| Opportunity Ranking | Present |
| Demand Opportunity Ranking | Present |
| Showcase | Present |

### Default runtime configuration

| Setting | Value |
|---------|-------|
| SupplierRuntimeConfig.default() | `use_fixture=True`, `enable_live=False` |
| DemandLookup | Fixture dir: `tests/fixtures/demand/` |
| Domestic market | FakeYahooAuctionClient via aggregator |
| Default supplier | fashionphile (fixture client) |

---

## Git Change Inventory

### Modified files (3)

| File | Change summary |
|------|----------------|
| `main.py` | +4 lines: `discovery` subcommand dispatch |
| `product_identity/models.py` | +11 lines: `ProductIdentity` dataclass (V2-11F) |
| `supplier/factory.py` | +18 lines: `resolve_supplier_client` with runtime config |

### Deleted files

None.

### Untracked files (~120+)

Major untracked directories from V2-7B through V2-12A:

- `profit_discovery/` — brand_catalog, category_catalog, cli, discovery_runner, market_connector, multi_brand, opportunity, showcase
- `profit_intelligence/demand/`
- `product_identity/` — identity_resolver.py, duplicate_resolver.py
- `supplier/` — adapters, config, fashionphile, live, overseas_new, therealreal, vestiaire
- `marketplace/` — domestic_market, yahoo_auction
- `tests/` — ~70 new test files + fixture directories

**Risk:** Entire V2 discovery stack is uncommitted on `develop/v2`. Branch tracks remote but local additions are not staged.

---

## Known Risks

1. **Uncommitted V2 work** — All V2-7B〜V2-12A features exist locally but are not in version control history on this branch.
2. **Fixture-only default** — Production live-mode paths (supplier live, real demand data) are configured but not smoke-tested in consolidation.
3. **Verbose CLI output** — Four display sections (Summary, TOP BUY, Demand Ranking, Showcase) print sequentially; operational tuning may be needed.
4. **Duplicate merge reduces rows** — Identity merge can produce fewer ranked opportunities than raw discovery candidates.
5. **product_identity dual purpose** — Legacy identity matching (ProductIdentityService) coexists with V2 duplicate resolution (ProductIdentityResolver); separate import paths.
6. **Four Excel sheets** — Export workbook grows with each ranking layer; consumers must know which sheet is authoritative.

---

## Next Phase Preparation

### Recommended before next implementation

1. **Commit consolidation** — Stage and commit V2-7B〜V2-12A as a single or phased commit series (when authorized).
2. **Branch hygiene** — Ensure `develop/v2` reflects full untracked tree before feature work continues.
3. **Live mode smoke** — Add optional live-mode verification behind env flags when credentials are available.
4. **Documentation sync** — Update `docs/02_ARCHITECTURE.md` and `docs/08_FOLDER_STRUCTURE.md` to reflect V2 packages.
5. **CLI UX review** — Consider making Showcase the primary view and demoting legacy Opportunity Ranking display.

### Test baseline (locked)

```
1948 passed, 33 warnings
```

Verified commands:

```bash
python -m pytest -q
python main.py discovery --brands Chanel --keyword wallet
```

### Forbidden layers (unchanged this phase)

- ProfitCalculator, BuyDecisionEngine, DiscoveryEngine, RankingEngine
- OpportunityScorer, DemandIntegratedOpportunityScorer
- supplier/* logic, marketplace/* logic

---

*Generated during V2-12A-1 safety check. No application logic was modified.*
