# Roadmap

## Phase 1

Project setup

Basic architecture

3 overseas stores

Excel export

---

## Phase 2

Japanese price comparison (local candidates)

Profit calculation

ROI

Ranking

Excel export for PriceResult

---

## Phase 3

Domestic marketplace listing models

Common marketplace search interface

Local marketplace candidates

Listing validation and matching

PriceComparator and ProfitCalculator integration

Domestic listings Excel export

---

## Phase 4

Yahoo Shopping Product Search API (v3) foundation

- YahooApiClient / YahooResponseParser / YahooMarketplace
- MarketplaceFactory `yahoo` support
- Optional Yahoo execution in main.py (default remains local)
- Mocked tests without external network access

Next domestic marketplace candidates:

- Rakuten Ichiba API
- Mercari (future research)

Note: Live Yahoo API verification with real credentials is a separate operational task.

---

## Phase 5

10 supported overseas stores

Automatic scheduling

Database

History

---

## Phase 6

GUI

Automatic update

Notification

Cloud deployment
