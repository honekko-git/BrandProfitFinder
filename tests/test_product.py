"""Foundation tests for models.product."""

from models.product import Product


def test_calculate_landed_cost_in_jpy() -> None:
    product = Product(
        name="Bag",
        brand="Demo",
        price=100.0,
        currency="USD",
        exchange_rate=150.0,
    )
    assert product.calculate_landed_cost() == 15000.0


def test_calculate_profit_and_roi() -> None:
    product = Product(
        name="Bag",
        brand="Demo",
        price=100.0,
        currency="USD",
        exchange_rate=100.0,
        yahoo_price=15000.0,
    )
    product.calculate_landed_cost()
    profit = product.calculate_profit()
    assert profit == 5000.0
    assert product.roi == 50.0


def test_best_japanese_price() -> None:
    product = Product(
        rakuten_price=20000.0,
        yahoo_price=18000.0,
        mercari_price=22000.0,
    )
    assert product.best_japanese_price() == 18000.0


def test_to_dict_contains_core_fields() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0)
    data = product.to_dict()
    assert data["name"] == "Bag"
    assert data["brand"] == "Demo"
    assert data["price"] == 100.0
