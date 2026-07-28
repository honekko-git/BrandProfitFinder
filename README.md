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