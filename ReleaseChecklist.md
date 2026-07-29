# BrandProfitFinder — Release Checklist

Version 1.0 Release Candidate (RC1) verification checklist.

Complete all items before tagging RC1 or promoting to production use.

---

## 1. Environment

- [ ] Python 3.11 or newer installed (`python --version`)
- [ ] Virtual environment created and activated
- [ ] Dependencies installed from unchanged `requirements.txt`:

```bash
pip install -r requirements.txt
```

- [ ] `.env` copied from `.env.example` (defaults OK for local/demo)
- [ ] `output/` and `logs/` directories writable

---

## 2. Code Quality

- [ ] No unintended changes to `requirements.txt`
- [ ] No debug print statements in production modules
- [ ] Public API signatures unchanged from Version 1 baseline
- [ ] Architecture safety tests pass (no forbidden cross-imports)

---

## 3. Automated Tests

### Full pytest

```bash
python -m pytest -q
```

- [ ] **Expected:** 1370+ passed, 0 failed
- [ ] Runtime: typically under 60 seconds

### Phase regression (20–25)

```bash
python -m pytest tests/test_product_identity_phase20.py tests/test_profit_policy_phase21.py tests/test_marketplace_search_phase22.py tests/test_import_cost_phase23.py tests/test_ranking_foundation_phase24.py tests/test_comparison_unification_phase25.py -q
```

- [ ] **Expected:** 59 passed

---

## 4. CLI Demos

Run sequentially (do not parallelize — shared Excel output path):

```bash
python main.py
python main.py --identity-demo
python main.py --comparison-demo
python main.py --comparison-demo --profit-intelligence
```

- [ ] All commands exit with code 0
- [ ] Default pipeline writes `output/profit_ranking.xlsx`
- [ ] Identity demo logs summary (match/review/no_match counts)
- [ ] Comparison demo logs `comparisons=3 comparable=5` (approximate)

Optional marketplace demos (when fixtures present):

```bash
python main.py --demo-stockx
python main.py --demo-goat
```

- [ ] Exit code 0

---

## 5. Workbook Validation

After comparison demo:

```bash
python scripts/validate_workbook_phase24.py
```

- [ ] Output contains: `workbook OK: 31 columns, 3 rows, 8 identity columns`
- [ ] No forbidden wording (authenticity, probability, Python repr leakage)
- [ ] No duplicate comparison rows
- [ ] Column order matches `excel/template.py`

---

## 6. Documentation

- [ ] [README.md](README.md) reflects Version 1 status
- [ ] [Architecture.md](Architecture.md) diagrams match current pipeline
- [ ] [DeveloperGuide.md](DeveloperGuide.md) setup steps verified locally
- [ ] [ExtensionGuide.md](ExtensionGuide.md) marketplace checklist current
- [ ] This checklist completed and archived with release notes

---

## 7. Release Artifacts

- [ ] Git branch reviewed (feature complete, tests green)
- [ ] Change summary prepared (Phases 18–25 + RC hardening)
- [ ] Known limitations documented (see below)
- [ ] Tag name decided (e.g. `v1.0.0-rc1`) — **requires explicit git write approval**

---

## Known Version 1 Limitations

| Item | Status |
|------|--------|
| `ranking_foundation_score` in metadata but not Excel column | Documented |
| Only StockX/GOAT use `MarketplaceAdapter` | By design |
| Comparison sort uses legacy lexicographic keys | Backward compatible |
| Live API requires manual `.env` configuration | Optional |
| Default execution uses fixtures only | By design |

---

## Troubleshooting

### pytest failures with network errors

Tests must not hit the network. Check for missing `@patch("utils.http.fetch_url")` or unmocked clients.

### `ModuleNotFoundError`

Run from repository root. Ensure virtual environment is active and `pip install -r requirements.txt` completed.

### Workbook validation fails: missing sheet

Run `python main.py --comparison-demo` before validation. Default `main.py` may not include comparison sheet.

### Workbook corrupted / unreadable

Do not run multiple CLI commands writing `output/profit_ranking.xlsx` concurrently.

### Identity demo shows unexpected NO_MATCH counts

Fixture set is synthetic and fixed. Compare against logged summary in prior green runs.

### Import errors for new packages

Ensure `__init__.py` exists and exports are listed in `__all__`.

---

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Developer | | | ☐ Pass |
| Reviewer | | | ☐ Pass |

**Recommendation criteria:**

- **READY FOR RC1** — all checklist items pass
- **READY WITH MINOR NOTES** — all tests/demos pass; minor doc or process gaps only
- **NOT READY** — test failures, demo failures, or API regressions

---

## Quick Verification Script

Run from repository root (PowerShell):

```powershell
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python main.py
python main.py --identity-demo
python main.py --comparison-demo
python scripts/validate_workbook_phase24.py
```

All steps must exit 0.
