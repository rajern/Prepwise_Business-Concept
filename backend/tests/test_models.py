from sqlalchemy import Numeric
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from prepwise_api.models import Base, Meal, OrderItem

EXPECTED_TABLES = {
    "allergens",
    "cart_items",
    "ingredients",
    "knowledge_chunks",
    "meal_allergens",
    "meal_ingredients",
    "meals",
    "order_items",
    "order_confirmations",
    "orders",
    "pickup_locations",
    "users",
}


def test_all_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_all_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl


def test_money_columns_use_fixed_precision() -> None:
    meal_price_type = Meal.__table__.c.price_nok.type
    order_item_price_type = OrderItem.__table__.c.unit_price_nok.type

    assert isinstance(meal_price_type, Numeric)
    assert meal_price_type.scale == 2
    assert isinstance(order_item_price_type, Numeric)
    assert order_item_price_type.scale == 2
