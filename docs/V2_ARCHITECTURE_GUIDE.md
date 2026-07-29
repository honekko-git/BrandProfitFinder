# Version 2 Architecture Guide

Permanent development reference for the BrandProfitFinder Version 2 foundation.

**Status:** Architecture freeze as of commit `d6eb7b2` (Phase V2-5D)  
**Baseline tests:** 1637 passed  
**Branch:** `develop/v2`

This document defines what must not change, where new features belong, and how to extend the system without breaking Version 2 contracts.

Related documents:

- `ExtensionGuide.md` — step-by-step extension recipes (Version 1 + V2 compatible)
- `docs/02_ARCHITECTURE.md` — high-level pipeline overview
- `docs/08_FOLDER_STRUCTURE.md` — directory responsibilities

---

## 1. Version 2 Architecture Overview

Version 2 separates **transport**, **client resolution**, **marketplace orchestration**, and **domain analysis** into distinct layers. Each layer has a single responsibility. Do not collapse layers or bypass them.

### End-to-end flow

```
CLI (main.py)
  ↓
Settings (config/settings.py, marketplace/*_settings.py)
  ↓
Factory (marketplace/marketplace_factory.py)
  ↓
Client Resolver (marketplace/marketplace_client_factory.py)
  ↓
Marketplace Client (*_client.py, *_api_client.py, Fake*Client)
  ↓
Transport (utils/transport/ — opt-in via *_USE_TRANSPORT flags)
  ↓
Parser / Adapter (*_response_parser.py, *_response_adapter.py, *_transport_mapper.py)
  ↓
Internal Models (models/* — MarketplaceListing, MarketplaceSearchResult, Product, PriceResult)
  ↓
Product Identity (product_identity/*)
  ↓
Profit Intelligence (profit_intelligence/* — optional scoring layer)
  ↓
Ranking (ranking_foundation/*, price_compare/ranking_engine.py)
  ↓
Output (excel/*, comparison/* formatters)
```

### Layer responsibilities

| Layer | Owns | Must NOT own |
|-------|------|--------------|
| **CLI** | Argument parsing, demo client builders, marketplace selection, pipeline orchestration | HTTP, signing, parsing, profit math |
| **Settings** | Environment flags, credentials presence, feature toggles (`*_USE_TRANSPORT`) | Business logic |
| **Factory** | Marketplace instance creation, alias normalization | Client selection logic (delegates to resolver) |
| **Client Resolver** | Fake vs live client selection priority | HTTP, transport, parsing |
| **Marketplace** | Search orchestration, listing validation, ranking within marketplace | Raw HTTP, transport retries |
| **ApiClient** | Auth, signing, request building, response delegation to parser/adapter | Retry/backoff policy (transport owns this when enabled) |
| **Transport** | HTTP execution, retry, timeout, backoff, secure logging | Authentication, signing, domain parsing |
| **Parser / Adapter** | External JSON → internal contract JSON → `MarketplaceListing` | Profit calculation, identity scoring |
| **Models** | Normalized data structures | Marketplace-specific API knowledge |
| **Profit / Ranking / Identity** | Domain analysis on normalized models | Marketplace API calls |

### Client resolver priority (frozen)

All domestic marketplaces routed through `marketplace_client_factory.py` follow this order:

1. **Explicit injected client** — tests, CLI demo builders, manual overrides (always wins)
2. **Demo client** — `Fake*Client` when demo mode is enabled (Rakuten, Amazon)
3. **Live API client** — `*ApiClient.from_settings()` when enabled and credentials are configured
4. **None** — marketplace handles missing client according to its existing error behavior

Yahoo Shopping has no demo fake in Version 2; resolver skips step 2 and uses live or none.

### Version 2 milestone map

| Phase | Deliverable |
|-------|-------------|
| V2-0 | Common transport foundation (`utils/transport/`) |
| V2-1 | Transport integration validation |
| V2-2 | Rakuten transport migration (`RAKUTEN_USE_TRANSPORT`) |
| V2-3 | Yahoo Shopping transport migration (`YAHOO_USE_TRANSPORT`) |
| V2-4 | Amazon live client foundation (`AMAZON_USE_TRANSPORT`, PA-API 5.0) |
| V2-5A | Unified client resolver |
| V2-5B | Factory parity validation |
| V2-5C | CLI production wiring validation |

---

## 2. Marketplace Extension Rules

### Adding a new domestic marketplace (example: `NewMarketplace`)

Follow the established file set. Do not skip layers or embed API logic in the marketplace class.

#### Required components

| Component | File pattern | Responsibility |
|-----------|--------------|----------------|
| Settings | `marketplace/new_settings.py` | Env-backed config, `is_configured`, `can_execute`, `can_demo`, `use_transport` |
| Exceptions | `marketplace/new_exceptions.py` | Typed errors mapped from HTTP/transport failures |
| Protocol + Fake client | `marketplace/new_client.py` | `NewClientProtocol`, `FakeNewClient` for tests and demo |
| API client | `marketplace/new_api_client.py` | Live HTTP, signing/auth, transport opt-in path |
| Transport mapper | `marketplace/new_transport_mapper.py` | Transport exception → marketplace exception |
| Response adapter | `marketplace/new_response_adapter.py` | Raw API JSON → internal parser contract (when needed) |
| Parser | `marketplace/new_response_parser.py` | Internal JSON → `MarketplaceListing` |
| Marketplace | `marketplace/new_marketplace.py` | `BaseMarketplace` implementation, search pipeline |
| Factory registration | `marketplace/marketplace_factory.py` | `create_marketplace("new", ...)` entry |
| Resolver registration | `marketplace/marketplace_client_factory.py` | `resolve_new_client()` with standard priority |
| Config | `config/settings.py`, `.env.example` | Feature flags and credentials |
| Tests | `tests/test_new_*.py` | Client, parser, transport parity, factory, integration |

#### Integration checklist

1. Add constants to `config/constants.py` (`MARKETPLACE_NEW`)
2. Implement `resolve_new_client()` in `marketplace_client_factory.py`
3. Wire `create_marketplace()` and `get_all_marketplaces()` in `marketplace_factory.py`
4. Add CLI demo support in `main.py` only when demo fixtures exist (`build_new_demo_client()`, `--demo-new`)
5. Add transport parity tests (legacy path vs `*_USE_TRANSPORT=true`)
6. Add factory parity tests (injection, demo, live, none)
7. Update `.env.example` with new flags

#### Forbidden shortcuts

Do **not**:

- Call `httpx` directly from `*_marketplace.py`
- Put signing or authentication inside `utils/transport/`
- Parse raw API responses inside `*_api_client.py` beyond adapter delegation
- Add marketplace-specific fee or margin logic inside the marketplace class
- Bypass the resolver by constructing `*ApiClient` inside `create_*_marketplace()` helpers
- Create `HttpTransport` inside the resolver or factory
- Default unknown shipping, fees, or currency to zero — use `None` and explicit flags
- Modify existing parser contracts for other marketplaces when adding a new one

#### Recommended path for comparison-ready marketplaces

For marketplaces participating in cross-marketplace comparison with structured identity, extend `MarketplaceAdapter` (see `ExtensionGuide.md` Path B). Comparison service routes adapters through `MarketplaceSearchService`.

---

## 3. Supplier Integration Rules

Version 2 domestic marketplace patterns extend naturally to **overseas sourcing suppliers**. Suppliers are input-side integrations; marketplaces are output-side (domestic sale price) integrations.

### Supplier flow (target pattern)

```
Supplier (business entity — e.g. Cettire, Baltini, used-luxury provider)
  ↓
Supplier Client (scanner/* or dedicated supplier client module)
  ↓
Transport (utils/transport/ when live HTTP is required)
  ↓
Adapter (supplier-specific raw → normalized structure)
  ↓
Normalized Product (models/product.py)
```

### Supplier categories

| Category | Location today | Extension pattern |
|----------|----------------|-------------------|
| Overseas new goods | `scanner/` (`cettire.py`, `baltini.py`, `italist.py`) | New scanner + `scanner_factory.py` registration |
| Overseas used brand | `marketplace/used_luxury_*`, comparison demo providers | Provider client + adapter → `Product` |
| Domestic sourcing site | Future module | Same client → transport → adapter → `Product` pattern |

### Supplier rules

1. **Output is always `Product`** — downstream profit, identity, and ranking consume normalized products, not raw HTML/JSON.
2. **No supplier logic in profit or ranking layers** — convert first, analyze second.
3. **Fixtures for tests** — no live network in unit tests; use `tests/fixtures/`.
4. **Register in factory** — `scanner/scanner_factory.py` or a dedicated supplier registry; do not hardcode supplier selection in `main.py` beyond CLI flags.
5. **Transport when live** — reuse `HttpTransport`; do not duplicate retry/backoff in supplier clients.
6. **Keep scanners thin** — parsing and normalization belong in adapter/parser modules when complexity grows.

### Adding a new overseas supplier

1. Create `scanner/<supplier>.py` extending `BaseScanner`
2. Register in `scanner/scanner_factory.py`
3. Add fixture data under `tests/fixtures/`
4. Add `tests/test_<supplier>.py`
5. If live HTTP is needed later, add `<supplier>_api_client.py` with transport opt-in (mirror marketplace pattern)
6. Do not modify `ProfitCalculator` or `RankingEngine` for supplier-specific behavior

---

## 4. Profit Engine Rules

The profit engine operates on **normalized listings and products only**. Marketplace integrations must finish parsing and validation before profit analysis begins.

### Pipeline contract

```
Marketplace.search(product)
  → MarketplaceSearchResult
    → valid_listings: list[MarketplaceListing]
      → calculate_profit_from_search_results()
        → PriceResult
          → RankingEngine.rank()
            → optional ProfitIntelligenceService.enrich()
```

### Frozen rules

1. **`MarketplaceListing` is the boundary** — all fee, shipping, and price fields must be populated (or explicitly `None`) at listing creation time.
2. **No marketplace-specific logic in:**
   - `price_compare/profit_calculator.py`
   - `price_compare/ranking_engine.py`
   - `product_identity/*`
   - `profit_intelligence/*`
3. **Marketplace-specific economics** belong in `price_compare/profit_config.py` and `profit_policy/` — register via `marketplace_configurations()`.
4. **Identity extraction** uses `product_identity/extractor.py` on `MarketplaceListing` — do not embed identity heuristics in parsers unless producing listing fields (`jan_code`, `model_number`, etc.).
5. **Profit Intelligence is optional** — enabled via CLI flag; must not change base profit numbers, only add scoring metadata.
6. **Points and promotions** — record on listing metadata; do not silently deduct from profit unless policy explicitly configures it.

### Extension pattern for profit analysis

| Extension | Where to add |
|-----------|--------------|
| New fee model | `profit_policy/`, register in `profit_config.py` |
| New ranking weight | `ranking_foundation/policy.py` or `ProfitConfig` fields |
| New intelligence signal | `profit_intelligence/` scorer module + `service.py` registration |
| New export column | `excel/template.py`, `excel/formatter.py` |

---

## 5. Transport Rules

Version 2 introduces a shared HTTP transport layer behind feature flags. Transport is opt-in per marketplace (`RAKUTEN_USE_TRANSPORT`, `YAHOO_USE_TRANSPORT`, `AMAZON_USE_TRANSPORT`).

### HttpTransport responsibilities (`utils/transport/`)

- HTTP method execution (`get`, `post`)
- Retry with configurable backoff
- Timeout enforcement
- Secure logging (credential masking via `logging_utils.py`)
- Transport-level exception types (`utils/transport/exceptions.py`)

### ApiClient responsibilities (`*_api_client.py`)

- Credential validation and configuration checks
- Request construction (params, headers, body)
- Authentication and signing (e.g. Rakuten Bearer token, Amazon SigV4)
- Choosing legacy httpx path vs transport path based on `use_transport` flag
- Delegating response parsing to adapter/parser — not domain modeling

### Frozen separation

| Concern | Owner |
|---------|-------|
| SigV4 / Bearer / API keys | ApiClient |
| Retry / backoff / timeout | HttpTransport (when enabled) |
| Raw JSON → internal contract | Response adapter |
| Internal contract → listings | Response parser |
| Transport errors → domain errors | Transport mapper (`*_transport_mapper.py`) |

**Never move signing into transport.**  
**Never move retry policy into marketplace classes.**

### Adding transport to a new integration

1. Add `*_USE_TRANSPORT` flag to `config/settings.py` and `.env.example` (default `false`)
2. Implement `_perform_transport_request()` in `*_api_client.py`
3. Add `*_transport_mapper.py` for exception mapping
4. Add parity tests: legacy path vs transport path must produce identical parser input
5. Add enable tests: flag propagation from factory/resolver → ApiClient → HttpTransport

---

## 6. Cursor Development Rules

Rules for AI-assisted and human development on this codebase.

### Before modifying code

1. **Inspect before modifying** — read surrounding files, existing tests, and this guide
2. **Identify the correct layer** — if unsure, check Section 1 flow diagram
3. **Check forbidden zones** — do not edit frozen layers without explicit phase approval

### During implementation

4. **Prefer extension over rewrite** — add files, register in factories; do not refactor unrelated code
5. **Preserve tests** — all existing tests must pass; add new tests for new behavior
6. **Do not bypass failures** — fix root cause; do not weaken assertions to make tests pass
7. **Minimize diff scope** — one concern per change; match existing naming and patterns
8. **Mock HTTP in tests** — use `httpx.MockTransport`, patch `HttpTransport`, or fake clients; no live API calls in CI

### Phase workflow

9. **Commit per phase** — one logical phase per commit with descriptive message
10. **Tag milestones** — tag stable phase completions (e.g. `phase25c-cli-factory-wiring`)
11. **No commit unless requested** — during development sessions, wait for explicit commit instruction
12. **Regression before finish** — always run `python -m pytest -q` before reporting completion

### Version 2 frozen modules (do not redesign without new phase)

- `utils/transport/*` — transport contract
- `marketplace/marketplace_client_factory.py` — resolver priority order
- `marketplace/marketplace_factory.py` — factory entry points
- `models/*` — public model fields used by Excel export and profit pipeline
- `product_identity/*` — identity extraction contract
- `profit_intelligence/*` — scoring service interface
- `ranking_foundation/*` — ranking policy contract

---

## 7. Future Roadmap

Post-V2-5 development direction. Each phase requires its own spec, tests, and milestone tag.

### Phase 26 — Profit Discovery Engine enhancement

- Expand deterministic profit discovery signals beyond current `ProfitIntelligenceService`
- Richer velocity, risk, and confidence scoring on normalized `PriceResult` data
- No LLM dependency; rule-based and explainable
- Must not alter base profit calculation outputs

### Phase 27 — Overseas sourcing integration

- Live supplier clients using Version 2 transport pattern
- Unified supplier registry parallel to marketplace factory
- Normalized `Product` pipeline from supplier adapter
- Integration with existing scanner fixtures-first workflow

### Phase 28 — Brand intelligence

- Brand-level aggregation across marketplaces and suppliers
- Identity confidence enrichment using `product_identity/` outputs
- Comparison service extensions for brand-aware matching
- Separate from authenticity determination

### Phase 29 — Automation / AI discovery

- Optional AI-assisted query and product discovery (explicit opt-in)
- Must remain separated from deterministic profit and ranking core
- AI outputs feed suggestions only; never override calculated profit numbers
- Human-reviewable explanation artifacts

---

## Quick Reference — Where Does My Change Go?

| I want to… | Module |
|------------|--------|
| Add a domestic marketplace | `marketplace/new_*`, factory, resolver, tests |
| Add an overseas store scanner | `scanner/new.py`, `scanner_factory.py` |
| Change fee or tax rules | `profit_policy/`, `price_compare/profit_config.py` |
| Change ranking weights | `ranking_foundation/`, `price_compare/ranking_engine.py` |
| Add intelligence scoring | `profit_intelligence/` |
| Change HTTP retry behavior | `utils/transport/retry.py` (affects all transport users) |
| Add API signing | `marketplace/*_api_client.py` or `*_request_signer.py` |
| Change Excel output | `excel/template.py`, `excel/exporter.py` |
| Add CLI flag | `main.py`, `config/settings.py`, `.env.example` |
| Add environment variable | `config/settings.py`, `.env.example`, marketplace settings |

---

## Architecture Freeze Declaration

As of Phase V2-5D:

- The **layer separation** defined in Section 1 is frozen.
- The **client resolver priority** defined in Section 1 is frozen.
- The **transport vs ApiClient boundary** defined in Section 5 is frozen.
- The **profit pipeline contract** defined in Section 4 is frozen.

Extensions must add new files and factory registrations. Changes to frozen contracts require a new numbered phase with explicit approval, parity tests, and regression validation.

**Regression baseline:** 1637 tests passing on `develop/v2` at commit `d6eb7b2`.
