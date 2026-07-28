# Data Model

## Product

Represents one product collected from any supported overseas store.

---

## Fields

### Basic

name : str

brand : str

model : str

sku : str

category : str

gender : str

---

### Price

price : float

currency : str

shipping_cost : float

tax_cost : float

fee_cost : float

exchange_rate : float

landed_cost : float

---

### Japanese Price

rakuten_price : float | None

yahoo_price : float | None

mercari_price : float | None

ebay_price : float | None

---

### Profit

profit : float

roi : float

margin : float

---

### Store

store_name : str

country : str

url : str

image_url : str

---

### Status

in_stock : bool

scraped_at : datetime

last_updated : datetime

---

## Design Rules

Every scanner must return Product objects.

Never return dictionaries.

Never return tuples.

Never return raw JSON.

Always convert scraped data into Product.

---

## Future Fields

barcode

color

size

season

material

weight

dimensions

condition
