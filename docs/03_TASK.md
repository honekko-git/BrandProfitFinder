# TASK LIST

## Phase 1

- [x] Create project structure
- [x] Configure Git
- [x] Configure Python
- [x] Configure logging
- [x] Create settings module
- [x] Create models
- [x] Create Excel exporter
- [x] Create scanner interface
- [x] Create Cettire scanner
- [x] Create Baltini scanner
- [x] Create Italist scanner

---

## Phase 2

- [x] Compare Japanese prices
- [x] Calculate profit
- [x] Calculate ROI
- [x] Export ranking

---

## Phase 3

- [x] MarketplaceListing model
- [x] MarketplaceSearchResult model
- [x] BaseMarketplace interface
- [x] LocalMarketplace implementation
- [x] MarketplaceFactory
- [x] ListingValidator
- [x] ListingMatcher
- [x] PriceComparator integration
- [x] ProfitCalculator integration
- [x] Domestic listings Excel export
- [ ] Support 10 overseas stores

---

## Phase 4

- [x] Yahoo Shopping Product Search API (v3) settings
- [x] YahooApiClient with mocked HTTP tests
- [x] YahooResponseParser (hits to MarketplaceListing)
- [x] YahooMarketplace (search, validator, matcher integration)
- [x] MarketplaceFactory yahoo registration
- [x] main.py optional Yahoo mode (`YAHOO_API_ENABLED` or `--marketplace yahoo`)
- [x] Local JSON fixtures for Yahoo responses
- [x] ProfitCalculator / PriceComparator / Excel integration tests
- [ ] Rakuten marketplace API
- [ ] Mercari marketplace API
- [ ] Live Yahoo API verification in production environment

### Phase 4 test status

- Total tests: 313 (including prior 223 regression tests)
- External HTTP is fully mocked in tests (`httpx.MockTransport`)
- Default `python main.py` and pytest use local marketplace only
- When `YAHOO_API_ENABLED=true` without Client ID, main.py falls back to local marketplace

### Yahoo API setup

Set values in `.env` (see `.env.example`):

- `YAHOO_CLIENT_ID` — Yahoo application ID (required for live API)
- `YAHOO_API_ENABLED=true` — enable Yahoo marketplace in main.py
- Or run: `python main.py --marketplace yahoo`

---

## Phase 5A

- [x] Amazon.co.jp domestic marketplace foundation (API-agnostic)
- [x] AmazonClientProtocol and FakeAmazonClient
- [x] AmazonResponseParser (internal standard JSON)
- [x] AmazonMarketplace with Validator/Matcher integration
- [x] MarketplaceFactory `amazon_jp` registration
- [x] Amazon price normalizer (JPY)
- [x] Excel domestic listings columns extended
- [x] Optional Amazon demo mode in main.py
- [ ] Live Amazon API connection (Creators API / SP-API)
- [ ] Amazon selling fee calculation
- [ ] Used-item common foundation

### Phase 5A test status

- Total tests: 398 (including prior 313 regression tests)
- No external Amazon API calls in tests or default main.py
- Demo mode uses `tests/fixtures/amazon_search_*.json`

---

## Phase 6

- [x] Rakuten Ichiba Item Search API (2026-07-01) settings
- [x] RakutenApiClient with header-based accessKey auth
- [x] FakeRakutenClient for tests and demo mode
- [x] RakutenResponseParser (formatVersion=2)
- [x] RakutenMarketplace with Validator/Matcher integration
- [x] MarketplaceFactory `rakuten` registration
- [x] Optional Rakuten demo mode in main.py
- [x] Excel domestic listings `point_rate` column
- [ ] Live Rakuten API verification in production environment
- [ ] Rakuten selling fee calculation
- [ ] Mercari marketplace API

### Phase 6 test status

- Total tests: 482 (including prior 398 regression tests)
- External HTTP is fully mocked in tests
- Default `python main.py` uses local marketplace only
- Demo: `python main.py --marketplace rakuten --demo-rakuten`

---

## Phase 7

- [x] Yahoo!オークション domestic marketplace foundation (API-agnostic)
- [x] YahooAuctionClientProtocol and FakeYahooAuctionClient
- [x] YahooAuctionResponseParser (internal standard JSON)
- [x] YahooAuctionMarketplace with Validator/Matcher integration
- [x] MarketplaceFactory `yahoo_auction` registration (aliases: `yahoo-auction`, `yahooauction`, `auctions`)
- [x] Optional Yahoo Auction demo mode in main.py
- [x] Excel domestic listings auction columns (`current_price_jpy`, `buy_now_price_jpy`, `winning_price_jpy`, etc.)
- [ ] Official API or licensed data provider connection
- [ ] Yahoo Auction selling fee calculation
- [ ] Detailed used-item condition grading

### Phase 7 test status

- Total tests: 482+ (including prior regression tests)
- No external Yahoo Auction API calls in tests or default `main.py`
- No scraping or browser automation
- Demo: `python main.py --marketplace yahoo_auction --demo-yahoo-auction`
- `current_price` is provisional; `winning_price` is used for sold listings
- Unknown shipping is not treated as free shipping

---

## Phase 8

- [x] Used luxury common domain models (condition, defects, accessories, authentication, seller, risk)
- [x] ConditionNormalizer with confidence and warnings
- [x] ConditionScorer (comparison aid, not auto-applied to profit)
- [x] UsedItemRiskEvaluator (warnings, not counterfeit declarations)
- [x] PriceAdjustmentCalculator (suggestions only, applied=false)
- [x] UsedItemDetails on MarketplaceListing (optional, backward compatible)
- [x] ListingValidator/Matcher/ProfitService/Excel integration
- [x] FakeUsedLuxuryProvider demo with internal standard JSON fixtures
- [x] Demo: `python main.py --marketplace used_demo --demo-used-luxury`
- [ ] Vestiaire Collective / Fashionphile / The RealReal / Grailed site clients
- [ ] Category-specific accessory requirement rules
- [ ] Auto-apply condition adjustments to profit (explicit opt-in future phase)

### Phase 8 test status

- Total tests: 575+ (including prior regression tests)
- No external site communication in tests or default `main.py`
- Demo uses fixture JSON only; default run unchanged

---

## Phase 9

- [x] Vestiaire Collective integration foundation (no live communication)
- [x] VestiaireClientProtocol and FakeVestiaireClient
- [x] VestiaireResponseParser (BrandProfitFinder internal standard JSON)
- [x] VestiaireMarketplace with pagination, duplicate exclusion, sale status filter
- [x] Phase 8 UsedItemEnricher integration for condition, defects, auth, risk
- [x] MarketplaceFactory aliases: vestiaire, vestiaire_collective, vestiaire-collective, vc
- [x] Demo: `python main.py --marketplace vestiaire --demo-vestiaire`
- [ ] Official Vestiaire API, partner data feed, or CSV import client
- [ ] Currency conversion for non-JPY listings (explicit opt-in)

### Phase 9 test status

- Total tests: 681+ (including prior regression tests)
- No external Vestiaire communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 10

- [x] Fashionphile integration foundation (no live communication)
- [x] FashionphileClientProtocol and FakeFashionphileClient
- [x] FashionphileResponseParser (BrandProfitFinder internal standard JSON)
- [x] FashionphileMarketplace with pagination, inventory/sale status, discount filters
- [x] Phase 8 UsedItemEnricher integration; inventory/discount in source metadata
- [x] MarketplaceFactory aliases: fashionphile, fashion_phile, fashion-phile, fp
- [x] Demo: `python main.py --marketplace fashionphile --demo-fashionphile`
- [ ] Official Fashionphile API, partner data feed, or CSV import client
- [ ] Currency conversion for non-JPY listings (explicit opt-in)

### Phase 10 test status

- Total tests: 741+ (including prior regression tests)
- No external Fashionphile communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 11

- [x] The RealReal integration foundation (no live communication)
- [x] TheRealRealClientProtocol and FakeTheRealRealClient
- [x] TheRealRealResponseParser (BrandProfitFinder internal standard JSON)
- [x] TheRealRealMarketplace with pagination, inventory/sale/final sale filters
- [x] Phase 8 UsedItemEnricher integration; final_sale in source metadata
- [x] MarketplaceFactory aliases: therealreal, the_real_real, the-real-real, realreal, trr
- [x] Demo: `python main.py --marketplace therealreal --demo-therealreal`
- [ ] Official The RealReal API, partner data feed, or CSV import client

### Phase 11 test status

- Total tests: 806+ (including prior regression tests)
- No external The RealReal communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 12

- [x] Grailed integration foundation (no live communication)
- [x] GrailedClientProtocol and FakeGrailedClient
- [x] GrailedResponseParser (BrandProfitFinder internal standard JSON)
- [x] GrailedMarketplace with pagination, inventory/sale/offer/seller filters
- [x] Phase 8 UsedItemEnricher integration; offer and seller metadata in source fields
- [x] MarketplaceFactory aliases: grailed, grailed_market, grailed-market, gr
- [x] Demo: `python main.py --marketplace grailed --demo-grailed`
- [ ] Official Grailed API, partner data feed, or CSV import client

### Phase 12 test status

- Total tests: 849+ (including prior regression tests)
- No external Grailed communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 13

- [x] Chrono24 integration foundation (no live communication)
- [x] Chrono24ClientProtocol and FakeChrono24Client
- [x] Chrono24ResponseParser (BrandProfitFinder internal standard JSON)
- [x] Chrono24Marketplace with pagination, watch details, negotiation/seller filters
- [x] Phase 8 UsedItemEnricher integration; watch metadata in source fields
- [x] MarketplaceFactory aliases: chrono24, chrono_24, chrono-24, c24
- [x] Matcher reference_number scoring and Chrono24 comparison warnings
- [x] Demo: `python main.py --marketplace chrono24 --demo-chrono24`
- [ ] Official Chrono24 API, partner data feed, or CSV import client

### Phase 13 test status

- Total tests: 903+ (including prior regression tests)
- No external Chrono24 communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 14

- [x] Farfetch integration foundation (no live communication)
- [x] FarfetchClientProtocol and FakeFarfetchClient
- [x] FarfetchResponseParser (BrandProfitFinder internal standard JSON)
- [x] FarfetchMarketplace with pagination, boutique/inventory/discount/duties filters
- [x] product_id / variant_id / style_code metadata; retail-focused condition handling
- [x] MarketplaceFactory aliases: farfetch, far_fetch, far-fetch, ff
- [x] Matcher style_code scoring; Farfetch comparison warnings
- [x] Demo: `python main.py --demo-farfetch`
- [ ] Official Farfetch API, partner data feed, CSV import, or manual import client

### Phase 14 test status

- Total tests: 990+ (including prior regression tests)
- No external Farfetch communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 15

- [x] StockX integration foundation (no live communication)
- [x] StockXClientProtocol and FakeStockXClient
- [x] StockXResponseParser (BrandProfitFinder internal standard JSON)
- [x] StockXMarketplace with pagination, market data, size/condition filters
- [x] lowest ask / highest bid / last sale separation; price source handling
- [x] MarketplaceFactory aliases: stockx, stock_x, stock-x, sx
- [x] Matcher size/size_system warnings; market stats excluded from identity
- [x] Demo: `python main.py --demo-stockx`
- [ ] Official StockX API, partner data feed, CSV import, or manual import client

### Phase 15 test status

- Total tests: 1038+ (including prior regression tests)
- No external StockX communication in tests or default `main.py`
- Internal fixture JSON only; not claimed as official API format

---

## Phase 16

- [x] Profit Intelligence v1 deterministic scoring engine (`profit_intelligence/`)
- [x] Component scorers: profit, velocity, risk, confidence
- [x] Recommendation engine with cautious review labels and 1–5 stars
- [x] ProfitIntelligenceService adapters from PriceResult and marketplace metadata
- [x] Pipeline integration after profit calculation; optional intelligence ranking
- [x] CLI: `--profit-intelligence` and alias `--ai-score`
- [x] Excel intelligence columns appended when scoring enabled
- [x] Scoring version constant: `profit-intelligence-v1`

### Phase 16 scoring behavior

- Not an LLM, ML model, or prediction guarantee
- Confidence reflects data completeness, not predicted success probability
- Risk score: 0 = lower observed risk, 100 = higher observed risk
- Unavailable component scores export as blank, never as zero
- Profit calculations, listings, and validation remain unchanged when scoring is disabled

### Phase 16 test status

- Comprehensive unit and integration tests under `tests/test_profit_intelligence_*.py`
- No scraping, live communication, or profit-calculation changes introduced

---

## Phase 17

- [x] GOAT marketplace foundation (no live communication)
- [x] GoatClientProtocol and FakeGoatClient (synthetic internal fixtures only)
- [x] GoatResponseParser (BrandProfitFinder internal standard JSON)
- [x] GoatMarketplace with conservative condition/box normalization
- [x] MarketplaceFactory aliases: goat, goat_marketplace, goat-marketplace
- [x] Demo: `python main.py --demo-goat`
- [x] Profit Intelligence optional integration via `--profit-intelligence`
- [ ] Official GOAT API, partner data feed, CSV import, or manual import client

### Phase 17 limitations

- Internal fixture JSON only; not claimed as official GOAT API format
- No scraping, browser automation, or network access
- No automatic currency conversion for non-JPY fixture prices
- Unknown shipping/fees/duties/tax remain unknown in profit calculation
- Profit Intelligence remains advisory decision-support metadata only

### Phase 17 test status

- Comprehensive unit and integration tests under `tests/test_goat_*.py`
- No external GOAT communication in tests or default `main.py`

---

## Phase 18

- [x] Cross-marketplace comparison foundation (`comparison/`)
- [x] `CrossMarketplaceComparisonService` consuming existing marketplace outputs
- [x] Deterministic identity matching via `ListingMatcher`
- [x] Comparison ranking: intelligence (when present), profit, margin, completeness, warnings, stable order
- [x] Currency safety: non-JPY amounts never treated as JPY; no automatic conversion
- [x] Honest output fields: `selected_review_*` vs `highest_profit_*` (no misleading best label)
- [x] Optional Profit Intelligence integration (consumes, does not replace)
- [x] Excel **Marketplace Comparison** sheet appended when comparison enabled
- [x] CLI demo: `python main.py --comparison-demo` (alias: `--demo-comparison`)

### Phase 18 limitations

- Demo uses synthetic StockX + GOAT fixtures only
- No live multi-marketplace orchestration API
- Recommendations are advisory review labels only
- `best_marketplace` remains a compatibility alias for `selected_review_marketplace`
- P3-003 used StockX listing may be excluded when preowned filtering is disabled
- Sequential CLI validation required when reopening `output/profit_ranking.xlsx`
- Future marketplaces require only marketplace adapter + comparison config entry

### Phase 18 test status

- Comprehensive tests under `tests/test_comparison_*.py`
- No network, scraping, or profit-formula changes introduced

---
