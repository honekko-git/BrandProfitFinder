# BrandProfitFinder Version 1.0 Release Notes

**Tag:** `v1.0.0`  
**Status:** READY FOR VERSION 1.0 (validated on real Fashionphile workspace data)

---

## Main capabilities

- Fashionphile acquisition via Chrome Extension (visible search cards → local workspace)
- Acquisition workspace: import, dedupe, budget/FX snapshot, continuous profit analysis
- Domestic sold comparables from Yahoo Auctions and Mercari
- Model-first JP/EN query generation (reference → collection/family → controlled category fallback)
- Sold-only filtering, junk exclusion, identity matching, comparable-quality publish gate
- New-market validation and trust/risk display
- Ranking of HIGH-confidence publishable opportunities (analysis version **v3**)

---

## Real-data validation metrics

Workspace: `ws-20260731183118-b673ef`

| Metric | Result |
|--------|--------|
| Workspace total | 410 |
| Eligible analyzed (v3) | 278 / 278 |
| Published selling prices | 64 |
| Published quality | 64 HIGH |
| Confirmed false positives | 0 |
| ¥7,975 contamination | 0 |
| Continuous analysis duration | ~43.7 minutes |

Evidence: `output/version1_validation.json`, `output/version1_scorecard.json`, `output/version1_false_positive.json`, `output/version1_false_negative.json`

---

## Known limitations

- Many candidates remain unpublished by design (SUSPECT / INSUFFICIENT) when comps are category-weak or thin
- Standard CostProfile may leave net profit provisional (gross/ROI still available)
- Live domestic search requires Playwright Chromium and network access
- Fashionphile capture covers currently visible cards only (no auto-scroll / private API scrape)
- No MEDIUM published tier observed in this workspace run (HIGH or blocked)

---

## Install and start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
playwright install chromium

python main.py web
```

Open `http://127.0.0.1:8000` → Acquisition Workspace. Use continuous analysis to process eligible candidates under the current analysis version.

---

## Chrome Extension reload

1. Open `chrome://extensions`
2. Enable Developer mode
3. Load unpacked → select the `chrome_extension` folder  
   (or click **Reload** on an existing BrandProfitFinder extension install)
4. Confirm BrandProfitFinder is running (`python main.py web`)
5. On Fashionphile search results, use **現在の検索結果を一括取込**

See `chrome_extension/README.md` for full usage notes.

---

## Safety confirmation

BrandProfitFinder Version 1.0 does **not**:

- perform automated purchasing, checkout, payment, or negotiation
- bypass CAPTCHA, login walls, or site access controls
- scrape private authenticated APIs for acquisition

Human challenges on Fashionphile (or other sites) must be completed by the user when required.
