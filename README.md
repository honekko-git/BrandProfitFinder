# BrandProfitFinder

## Overview

BrandProfitFinder is an AI-first Python application that discovers profitable luxury brand products by comparing overseas retailer prices with Japanese market prices.

The project is designed for autonomous AI-assisted development using Cursor.

---

## Goals

- Scan overseas luxury stores
- Compare prices with Japan
- Calculate expected profit
- Export Excel reports
- Support more than 30 stores
- Modular architecture
- AI Agent friendly

---

## Initial Stores

- Cettire
- Baltini
- Italist

---

## Future Stores

- Baltini
- Cettire
- Italist
- Coltorti
- Giglio
- MyTheresa
- FARFETCH
- Luisaviaroma
- 24S
- SSENSE
- Harrods
- Flannels
- END.
- Selfridges
- Neiman Marcus
- Saks Fifth Avenue
- Bloomingdale's
- Nordstrom
- CETTIRE AU
- and more...

---

## Tech Stack

Python 3.14

Git

Cursor

Requests

BeautifulSoup

Pandas

OpenPyXL

---

## Development Style

AI Agent First

Documentation Driven Development

Git Version Control

Incremental Development

---

## Status

Phase 7

Yahoo!オークション domestic marketplace foundation (API-agnostic, fixture-based)

Phase 8 adds used luxury brand common foundation (site-independent)

Phase 9 adds Vestiaire Collective integration foundation (fixture-based, no live API)

Phase 10 adds Fashionphile integration foundation (fixture-based, no live API)

Phase 13 adds Chrono24 integration foundation (fixture-based, no live API)

Phase 14 adds Farfetch integration foundation (fixture-based, no live API)

---

## Domestic Marketplaces

BrandProfitFinder compares overseas purchase prices with Japanese **sales** marketplaces.

| Marketplace | Role | Status |
|---|---|---|
| Yahoo Shopping | Domestic sales price comparison | API v3 (optional live) |
| Amazon.co.jp | Domestic sales price comparison | Phase 5A foundation (no live API) |
| Rakuten Ichiba | Domestic sales price comparison | Phase 6 foundation (no live API by default) |
| Yahoo!オークション | Domestic sales price comparison | Phase 7 foundation (no live API) |

Amazon is **not** an overseas sourcing store. Overseas sourcing stores are Cettire, Baltini, and Italist.

### Amazon Phase 5A notes

- No external Amazon API calls in tests or default `main.py` execution
- Does not use deprecated Product Advertising API 5.0 or PA-API SDKs
- Uses an internal standard JSON format parsed by `AmazonResponseParser`
- Live API connection (Creators API, Selling Partner API, etc.) is a future phase
- Amazon points are stored but **not** auto-deducted from profit
- Amazon selling fees are **not** auto-calculated in this phase

### Amazon demo mode (optional)

Set in `.env` (see `.env.example`):

```
AMAZON_JP_ENABLED=true
AMAZON_JP_DEMO_ENABLED=true
```

Or run:

```
python main.py --marketplace amazon_jp --demo-amazon
```

Demo mode uses local fixture JSON under `tests/fixtures/` and performs no network access.

When Amazon is not configured, `main.py` logs a skip message and continues with the existing local/Yahoo pipeline.

### Rakuten Ichiba Phase 6 notes

- API: Rakuten Ichiba Item Search API (`2026-07-01`)
- Requires `RAKUTEN_APPLICATION_ID` and `RAKUTEN_ACCESS_KEY` for live search
- `RAKUTEN_AFFILIATE_ID` is optional
- No external API calls in tests or default `main.py` execution
- Demo mode: `AMAZON_JP_ENABLED=true` is separate; for Rakuten use:

```
RAKUTEN_API_ENABLED=true
RAKUTEN_API_DEMO_ENABLED=true
```

Or:

```
python main.py --marketplace rakuten --demo-rakuten
```

- `postageFlag=0` → free shipping (`shipping_jpy=0`); otherwise shipping is unknown (`shipping_jpy=None`)
- Rakuten points (`pointRate`) are stored but **not** auto-deducted from profit
- Rakuten selling fees are **not** auto-calculated in this phase

### Yahoo!オークション Phase 7 notes

- Yahoo!オークション is a **domestic sales price comparison** target (not an overseas sourcing store)
- This phase is an **API-agnostic foundation** — it does **not** connect to an official public search API
- No unofficial scraping, browser automation, HTML parsing, or login cookies
- Demo mode uses local fixture JSON under `tests/fixtures/` (BrandProfitFinder internal standard JSON)
- `current_price` on active auctions is **provisional** and not a confirmed sold price
- `winning_price` is used for sold listings when available
- `free_shipping=true` → `shipping_jpy=0`; explicit shipping amount → that value; otherwise shipping is unknown (`shipping_jpy=None`, not treated as free)
- Yahoo Auction selling fees, bid increments, coupons, and PayPay points are **not** auto-calculated
- Future live data sources can replace `YahooAuctionClientProtocol` without changing Marketplace/Parser layers

### Yahoo!オークション demo mode (optional)

Set in `.env` (see `.env.example`):

```
YAHOO_AUCTION_ENABLED=true
YAHOO_AUCTION_DEMO_ENABLED=true
```

Or run:

```
python main.py --marketplace yahoo_auction --demo-yahoo-auction
```

When enabled without a live data source (`YAHOO_AUCTION_DATA_SOURCE`), `main.py` logs a skip message and continues without network access.

### Used Luxury Phase 8 notes

- Phase 8 is a **site-independent common foundation** for used luxury brand items
- Does **not** connect to Vestiaire Collective, Fashionphile, The RealReal, Grailed, or other specific sites
- No unofficial scraping, browser automation, HTML parsing, or login cookies
- Common models cover condition, defects, accessories, authentication, seller, returns, risk, and price adjustment suggestions
- **UNKNOWN** and missing information are distinct from "no problems"
- Seller claims are **not** treated as third-party authentication
- Condition score is a **comparison aid**, not a substitute for factual inspection
- Risk evaluation warns about concerns but does **not** declare items counterfeit
- Price adjustments are **suggestions only** (`adjustment_applied=false`); profit calculation is unchanged
- Demo mode uses internal standard JSON fixtures under `tests/fixtures/`

### Used luxury demo mode (optional)

```
USED_LUXURY_DEMO_ENABLED=true
```

Or:

```
python main.py --marketplace vestiaire --demo-vestiaire
```

### Vestiaire Collective Phase 9 notes

- Phase 9 is a **Vestiaire Collective integration foundation** (not a live site connection)
- Does **not** use official Vestiaire API format; internal standard fixture JSON only
- No scraping, browser automation, cookies, or unofficial access
- Reuses Phase 8 used luxury common models via `UsedItemEnricher`
- Seller claims are not treated as third-party authentication
- Risk evaluation warns but does not declare items counterfeit
- Price adjustment suggestions are not auto-applied to profit (`adjustment_applied=false`)
- Demo only: `--demo-vestiaire` with `FakeVestiaireClient`
- Without demo, `--marketplace vestiaire` logs a clear error and falls back safely

```
VESTIAIRE_DEMO_ENABLED=true
python main.py --marketplace vestiaire --demo-vestiaire
```

### Fashionphile Phase 10 notes

- Phase 10 is a **Fashionphile integration foundation** (not a live site connection)
- Does **not** use official Fashionphile API format; internal standard fixture JSON only
- Reuses Phase 8 used luxury models and Phase 9 integration patterns
- Inventory status and item condition are kept separate
- Discount and original price metadata are not auto-applied to profit (`discount_applied=false`)
- Price adjustment suggestions are not auto-applied (`adjustment_applied=false`)
- Demo only: `--demo-fashionphile` with `FakeFashionphileClient`
- Without demo, `--marketplace fashionphile` logs a clear error and falls back safely

```
FASHIONPHILE_DEMO_ENABLED=true
python main.py --marketplace fashionphile --demo-fashionphile
```

Or:

```
python main.py --demo-fashionphile
```

### The RealReal Phase 11 notes

- Phase 11 is a **The RealReal integration foundation** (not a live site connection)
- Does **not** use official The RealReal API format; internal standard fixture JSON only
- Reuses Phase 8 used luxury models and Phase 9/10 integration patterns
- Inventory status, item condition, final sale, and sale status are kept separate
- Discount metadata is not auto-applied to profit (`discount_applied=false`)
- Demo only: `--demo-therealreal` with `FakeTheRealRealClient`
- Without demo, `--marketplace therealreal` logs a clear error and falls back safely

```
THEREALREAL_DEMO_ENABLED=true
python main.py --marketplace therealreal --demo-therealreal
```

Or:

```
python main.py --demo-therealreal
```

### Grailed Phase 12 notes

- Phase 12 is a **Grailed integration foundation** (not a live site connection)
- Does **not** use official Grailed API format; internal standard fixture JSON only
- Reuses Phase 8 used luxury models and Phase 9–11 integration patterns
- Individual seller info, offers, inventory, discounts, and item condition are kept separate
- Offer/minimum offer and discount metadata are not auto-applied to profit (`offer_applied=false`, `discount_applied=false`)
- Seller claim and platform authentication are not conflated
- Demo only: `--demo-grailed` with `FakeGrailedClient`
- Without demo, `--marketplace grailed` logs a clear error and falls back safely

```
GRAILED_DEMO_ENABLED=true
python main.py --marketplace grailed --demo-grailed
```

Or:

```
python main.py --demo-grailed
```

### Chrono24 Phase 13 notes

- Phase 13 is a **Chrono24 integration foundation** (not a live site connection)
- Does **not** use official Chrono24 API format; internal standard fixture JSON only
- Reuses Phase 8 used luxury models and Phase 9–12 integration patterns
- Watch-specific metadata (reference number, movement, case diameter, etc.) kept in source fields
- Reference number and model number are distinguished; negotiation/discount not auto-applied to profit
- Seller claim, trusted seller, and platform authentication are not conflated
- Demo only: `--demo-chrono24` with `FakeChrono24Client`
- Without demo, `--marketplace chrono24` logs a clear error and falls back safely

```
CHRONO24_DEMO_ENABLED=true
python main.py --marketplace chrono24 --demo-chrono24
```

Or:

```
python main.py --demo-chrono24
```

### Farfetch Phase 14 notes

- Phase 14 is a **Farfetch integration foundation** (not a live site connection)
- Does **not** use official Farfetch API format; internal standard fixture JSON only
- No scraping, browser automation, cookies, or CAPTCHA bypass
- Reuses Phase 3–7 profit/compare and Phase 9–13 integration patterns
- `product_id`, `variant_id`, and `listing_id` are kept distinct; `style_code` and SKU are not conflated with JAN/model
- Unknown shipping/duties are not treated as zero; discounts/duties/variant prices are not auto-applied to profit
- Boutique metadata is informational only (not authenticity guarantee)
- `New Season` is season info, not a condition guarantee; Final Sale return rules handled safely
- Demo only: `--demo-farfetch` with `FakeFarfetchClient`
- Without demo, `--marketplace farfetch` logs a clear error and falls back safely

```
FARFETCH_DEMO_ENABLED=true
python main.py --marketplace farfetch --demo-farfetch
```

Or:

```
python main.py --demo-farfetch
```