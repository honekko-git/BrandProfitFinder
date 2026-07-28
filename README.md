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

Phase 5A

Amazon.co.jp domestic marketplace foundation (API-agnostic, fixture-based)

---

## Domestic Marketplaces

BrandProfitFinder compares overseas purchase prices with Japanese **sales** marketplaces.

| Marketplace | Role | Status |
|---|---|---|
| Yahoo Shopping | Domestic sales price comparison | API v3 (optional live) |
| Amazon.co.jp | Domestic sales price comparison | Phase 5A foundation (no live API) |

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