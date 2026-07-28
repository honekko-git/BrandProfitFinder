# Folder Structure

BrandProfitFinder/

├── config/
│   ├── settings.py
│   ├── constants.py
│   └── logging_config.py
│
├── docs/
│
├── scanner/
│   ├── base_scanner.py
│   ├── cettire.py
│   ├── baltini.py
│   ├── italist.py
│   └── scanner_factory.py
│
├── models/
│   ├── product.py
│   ├── price_result.py
│   └── ranking.py
│
├── price_compare/
│   ├── yahoo.py
│   ├── rakuten.py
│   ├── mercari.py
│   ├── ebay.py
│   └── compare.py
│
├── excel/
│   ├── exporter.py
│   ├── formatter.py
│   └── template.py
│
├── utils/
│   ├── http.py
│   ├── retry.py
│   ├── exchange_rate.py
│   ├── parser.py
│   ├── logger.py
│   └── validator.py
│
├── tests/
│
├── output/
│
├── logs/
│
├── main.py
├── requirements.txt
├── README.md
└── .gitignore

---

## Responsibilities

config

Project settings.

No business logic.

---

scanner

Collect products from overseas stores.

Return Product objects only.

---

models

Application data model.

No HTTP access.

---

price_compare

Search Japanese marketplaces.

Return normalized prices.

---

excel

Generate Excel reports.

No scraping logic.

---

utils

Reusable helper functions.

---

tests

Unit tests.

Integration tests.

---

logs

Runtime logs.

---

output

Generated Excel files.
