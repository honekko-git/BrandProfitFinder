# Git Baseline Plan

**Phase:** V2-12A-2 — Git Baseline Preparation & Commit Planning  
**Branch:** `develop/v2` (`aa2cd77`, tracks `origin/develop/v2`)  
**Remote:** `origin` → `https://github.com/honekko-git/BrandProfitFinder.git`  
**Date:** 2026-07-30  
**Test baseline:** 1948 passed (verified V2-12A-1)

> **Note:** This document is a planning artifact only. No commits or pushes were executed.

---

## Baseline Scope

### Modified tracked files (3)

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | +4 | Dispatch `python main.py discovery` to `run_discovery_cli` |
| `product_identity/models.py` | +11 | Add `ProductIdentity` dataclass (V2-11F) |
| `supplier/factory.py` | +18 | Add `resolve_supplier_client`, register TRR/Vestiaire |

### Untracked inventory (193 files)

| Category | Count | Description |
|----------|-------|-------------|
| **A. Production code** | 87 | Application modules (see breakdown below) |
| **B. Tests** | 87 | `tests/test_*.py` covering V2-7B〜V2-12A |
| **C. Fixtures** | 18 | `tests/fixtures/{demand,domestic_market,fashionphile,...}` |
| **D. Documentation** | 1 | `docs/runtime_consolidation_report.md` |
| **E. Temporary files** | 0 | None detected in untracked set |

**Deleted files:** None

---

## Classification Detail

### A. Production code (87 files)

#### `profit_discovery/` — 37 files

| Subpackage | Files | Phases |
|------------|-------|--------|
| `brand_catalog/` | 3 | V2-11A, V2-11B-1 |
| `category_catalog/` | 4 | V2-11B |
| `discovery_runner/` | 4 | V2-7B+ |
| `market_connector/` | 4 | V2-8+ |
| `multi_brand/` | 3 | V2-8+ |
| `opportunity/` | 10 | V2-10E〜V2-11E |
| `cli/` | 6 | V2-10F〜V2-11H |
| `showcase/` | 3 | V2-11H |

#### `profit_intelligence/demand/` — 5 files

| Module | Phases |
|--------|--------|
| `analyzer.py`, `lookup.py`, `models.py`, `resolver.py`, `__init__.py` | V2-11C〜V2-11E |

#### `product_identity/` — 2 files (untracked)

| Module | Phases |
|--------|--------|
| `identity_resolver.py`, `duplicate_resolver.py` | V2-11F |

*(Plus 1 modified tracked: `models.py`)*

#### `supplier/` — 29 files

| Subpackage | Files | Phases |
|------------|-------|--------|
| `adapters/` | 2 | V2-10+ |
| `config.py` | 1 | Runtime config |
| `fashionphile/` | 8 | V2-10D |
| `live/` | 5 | Live transport foundation |
| `overseas_new/` | 5 | Supplier models |
| `therealreal/` | 4 | V2-9+ |
| `vestiaire/` | 4 | V2-9+ |

*(Plus 1 modified tracked: `factory.py`)*

#### `marketplace/` — 16 files

| Subpackage | Files | Phases |
|------------|-------|--------|
| `domestic_market/` | 10 | V2-8+ aggregator |
| `yahoo_auction/` | 6 | V2-8+ adapter |

### B. Tests (87 files)

Grouped by domain:

| Domain | Count | Examples |
|--------|-------|----------|
| Discovery CLI | 8 | `test_discovery_cli*.py` |
| Multi-brand | 5 | `test_multi_brand_*.py` |
| Brand/Category catalog | 9 | `test_brand_catalog*.py`, `test_category_*.py` |
| Opportunity ranking | 9 | `test_opportunity_*.py` |
| Demand intelligence | 10 | `test_demand_*.py`, `test_sales_demand_*.py` |
| Identity / duplicate | 4 | `test_product_identity_resolver.py`, `test_duplicate_resolver.py`, `test_identity_*.py` |
| Showcase | 5 | `test_showcase_*.py` |
| Supplier adapters | 18 | `test_fashionphile_*.py`, `test_vestiaire_*.py`, etc. |
| Domestic market | 6 | `test_domestic_market_*.py`, `test_mercari_*.py` |
| Yahoo auction | 3 | `test_yahoo_auction_*.py` |
| Runtime stability | 1 | `test_runtime_stability.py` |
| Pipeline integration | 9 | `test_*_pipeline.py`, `test_cli_profit_integrity.py` |

### C. Fixtures (18 files)

| Directory | Count | Purpose |
|-----------|-------|---------|
| `tests/fixtures/demand/` | 6 | Sales demand profiles |
| `tests/fixtures/domestic_market/` | 2 | Mercari price snapshots |
| `tests/fixtures/fashionphile/` | 1 | Supplier product JSON |
| `tests/fixtures/therealreal/` | 3 | Supplier product JSON |
| `tests/fixtures/vestiaire/` | 3 | Supplier product JSON |
| `tests/fixtures/yahoo_auction/` | 3 | Domestic auction JSON |

### D. Documentation (1 file)

| File | Phase |
|------|-------|
| `docs/runtime_consolidation_report.md` | V2-12A-1 |

*(This plan file: `docs/git_baseline_plan.md` — V2-12A-2)*

### E. Temporary / generated files

**Status: Clean**

| Check | Result |
|-------|--------|
| `__pycache__/` in untracked | Not present |
| `.pytest_cache/` in untracked | Not present |
| `output/*.xlsx` in untracked | Not present (gitignored) |
| `.env` in untracked | Not present (gitignored) |
| `*.log` in untracked | Not present |

---

## Exclude

Do **not** include in baseline commits:

| Pattern | Reason |
|---------|--------|
| `output/*.xlsx` | Generated reports (gitignored) |
| `__pycache__/`, `*.pyc` | Python bytecode (gitignored) |
| `.pytest_cache/` | Test cache (gitignored) |
| `.env` | Secrets (gitignored) |
| `logs/`, `*.log` | Runtime logs (gitignored) |
| `.venv/`, `venv/` | Virtual env (gitignored) |
| `.cursor/`, `.vscode/` | IDE config (gitignored) |

---

## Suggested Commit Order

Commits are **planned only** — execute when authorized.

### Commit 1: Core pipeline foundation

**Message (suggested):** `Add discovery runner, market connector, and multi-brand orchestration (V2-7B–V2-8)`

```
profit_discovery/discovery_runner/
profit_discovery/market_connector/
profit_discovery/multi_brand/
tests/test_discovery_runner.py
tests/test_market_connector*.py
tests/test_multi_brand_*.py
tests/fixtures/yahoo_auction/
tests/fixtures/domestic_market/
```

**Depends on:** Nothing new (builds on existing tracked code)

---

### Commit 2: Supplier and marketplace layers

**Message (suggested):** `Add supplier adapters, runtime config, and domestic market aggregation (V2-9–V2-10D)`

```
supplier/adapters/
supplier/config.py
supplier/fashionphile/
supplier/live/
supplier/overseas_new/
supplier/therealreal/
supplier/vestiaire/
supplier/factory.py          (modified)
marketplace/domestic_market/
marketplace/yahoo_auction/
tests/fixtures/fashionphile/
tests/fixtures/therealreal/
tests/fixtures/vestiaire/
tests/test_fashionphile_*.py
tests/test_therealreal_*.py
tests/test_vestiaire_*.py
tests/test_supplier_*.py
tests/test_overseas_*.py
tests/test_domestic_market_*.py
tests/test_mercari_*.py
tests/test_yahoo_auction_*.py
```

---

### Commit 3: Discovery intelligence

**Message (suggested):** `Add brand/category catalogs, demand intelligence, identity resolution, and opportunity ranking (V2-11A–V2-11F)`

```
profit_discovery/brand_catalog/
profit_discovery/category_catalog/
profit_discovery/opportunity/
profit_intelligence/demand/
product_identity/identity_resolver.py
product_identity/duplicate_resolver.py
product_identity/models.py     (modified)
tests/fixtures/demand/
tests/test_brand_*.py
tests/test_category_*.py
tests/test_profit_brand_*.py
tests/test_demand_*.py
tests/test_sales_demand_*.py
tests/test_opportunity_*.py
tests/test_auto_demand_pipeline.py
tests/test_product_identity_resolver.py
tests/test_duplicate_resolver.py
tests/test_identity_pipeline.py
```

---

### Commit 4: CLI, entry point, and Showcase

**Message (suggested):** `Wire discovery CLI with demand-integrated pipeline and showcase dashboard (V2-10F–V2-11H)`

```
main.py                        (modified)
profit_discovery/cli/
profit_discovery/showcase/
tests/test_discovery_cli*.py
tests/test_opportunity_cli_integration.py
tests/test_opportunity_export.py
tests/test_opportunity_full_pipeline.py
tests/test_opportunity_consistency.py
tests/test_demand_cli_*.py
tests/test_identity_cli_integration.py
tests/test_showcase_*.py
tests/test_cli_profit_integrity.py
tests/test_runtime_stability.py
tests/test_*_pipeline.py       (remaining integration tests)
```

---

### Commit 5: Documentation

**Message (suggested):** `Add V2 runtime consolidation and git baseline planning docs (V2-12A)`

```
docs/runtime_consolidation_report.md
docs/git_baseline_plan.md
```

---

## Git Safety Confirmation

| Check | Value |
|-------|-------|
| Current branch | `develop/v2` |
| HEAD | `aa2cd77` — Phase V2-8E: Add multi supplier discovery service |
| Remote tracking | `origin/develop/v2` (up to date) |
| Remote URL | `https://github.com/honekko-git/BrandProfitFinder.git` |
| Staged changes | None |
| Uncommitted modified | 3 files |
| Untracked | 193 files (+ this plan = 194 after V2-12A-2) |
| Deleted | 0 |
| Commit executed | **No** |
| Push executed | **No** |

---

## Pre-Commit Checklist (when authorized)

1. Run `python -m pytest -q` — expect 1948 passed
2. Run `python main.py discovery --brands Chanel --keyword wallet` — smoke OK
3. Verify no `.env`, `output/*.xlsx`, or cache dirs staged
4. Review `git diff --cached --stat` before each commit
5. Push to `origin/develop/v2` only after all 5 commits pass CI locally

---

## Risks

1. **Monolithic alternative** — Single commit of 196 file touches is simpler but harder to review/revert.
2. **Cross-commit dependencies** — Commits 1→4 must be applied in order; partial baseline breaks imports.
3. **Test/fixture coupling** — Commit 1 without fixtures will fail pytest until Commit 2+ land.
4. **Modified tracked files span commits** — `factory.py` (Commit 2), `models.py` (Commit 3), `main.py` (Commit 4).
5. **Remote divergence** — Local branch is "up to date" but 193 files are invisible to remote until push.

---

## Pre Commit Validation

**Phase:** V2-12A-3 — executed 2026-07-30  
**Commit/push executed:** No

### Test result

```
1948 passed, 33 warnings in 34.56s
```

Baseline maintained. No regressions detected.

### Add scope verified (`git add -n .`)

| Metric | Value |
|--------|-------|
| Total files in dry-run | **197** |
| Modified tracked | 3 (`main.py`, `product_identity/models.py`, `supplier/factory.py`) |
| New untracked | 194 |

**Included (verified present in dry-run):**

| Path | Files |
|------|-------|
| `profit_discovery/` | 37 |
| `profit_intelligence/demand/` | 5 |
| `product_identity/` | 2 (+1 modified) |
| `supplier/` | 29 (+1 modified) |
| `marketplace/` | 16 |
| `tests/test_*.py` | 87 |
| `tests/fixtures/` | 18 |
| `docs/` | 2 |

**Excluded (verified absent from dry-run):**

| Pattern | Status |
|---------|--------|
| `output/` (incl. `*.xlsx`) | Not staged — gitignored |
| `.env` | Not staged — file absent; gitignored |
| `__pycache__/` | Not staged — gitignored |
| `.pytest_cache/` | Not staged — gitignored |
| `logs/` | Not staged — gitignored |
| `*.pyc` | Not staged — gitignored |
| `.venv/`, `venv/` | Not staged — gitignored |

### Secret scan result

| Check | Result |
|-------|--------|
| `.env` in add scope | **PASS** — not present |
| `tests/fixtures/` hardcoded secrets | **PASS** — no API keys/tokens in JSON fixtures |
| New supplier settings | **PASS** — `FASHIONPHILE_SUPPLIER_API_KEY` read from env only; no embedded credentials |
| Credential files (`.pem`, `.key`, `.credentials`) | **PASS** — none in add scope |

Note: Existing tracked test files contain synthetic test secrets (e.g. `"parity-test-access-key"`) — pre-existing, not part of V2 untracked scope.

### Large file result

| Check | Result |
|-------|--------|
| Files ≥ 50 MB in add scope | **PASS** — 0 files |
| Largest file | `main.py` — 55.8 KB |
| Total add-scope size | ~1.1 MB (estimated) |

### Import regression check

```
python -c "import profit_discovery"        → OK
python -c "import profit_intelligence"   → OK
python -c "import supplier"              → OK
python -c "import marketplace"           → OK
python -c "import product_identity"      → OK
```

All top-level package imports succeed.

### Ready status

| Item | Status |
|------|--------|
| Tests (1948) | **PASS** |
| Add scope clean | **PASS** |
| Secret scan | **PASS** |
| Large file check | **PASS** |
| Import regression | **PASS** |
| **Overall** | **READY FOR COMMIT** (when authorized) |

Proceed with the 5-commit plan in order. Run `git diff --cached --stat` after each `git add` before committing.

---

## Remote Push Verification

**Phase:** V2-12A-5 — executed 2026-07-30

| Item | Value |
|------|-------|
| Push date | 2026-07-30 |
| Remote | `origin` → `https://github.com/honekko-git/BrandProfitFinder.git` |
| Remote branch | `origin/develop/v2` |
| HEAD commit | `dd2fafb` — Add runtime and git baseline documentation |
| Push range | `aa2cd77..dd2fafb` (5 commits) |
| Test status (pre-push) | **1948 passed**, 33 warnings |

### Post-push verification

```
git status  → Your branch is up to date with 'origin/develop/v2'
git log --oneline --decorate -5:
  dd2fafb (HEAD -> develop/v2, origin/develop/v2) Add runtime and git baseline documentation
  71b13e0 Add production CLI and showcase output
  69cbb7e Add discovery intelligence and opportunity scoring
  7856205 Add supplier and marketplace integrations
  13a91ca Add core discovery pipeline foundation
```

Local and remote tracking refs aligned. Working tree clean at push time.

---

*Planning artifact — V2-12A-2 / validation V2-12A-3 / push V2-12A-5. No application logic modified.*
