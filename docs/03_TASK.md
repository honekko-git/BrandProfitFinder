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
