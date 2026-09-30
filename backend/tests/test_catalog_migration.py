import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def test_translation_migration_preserves_custom_catalogue_and_order_snapshots() -> None:
    path = (
        Path(__file__).parents[1] / "migrations/versions/d4e5f6a7b8c9_bilingual_catalog_pickup.py"
    )
    spec = importlib.util.spec_from_file_location("catalogue_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE meals (id TEXT PRIMARY KEY, name TEXT UNIQUE, description TEXT, "
                "price_nok NUMERIC, available BOOLEAN)"
            )
        )
        for table, columns in (
            ("ingredients", "name TEXT"),
            ("allergens", "name TEXT"),
            ("order_items", "meal_name TEXT"),
            ("order_confirmations", "id TEXT"),
        ):
            connection.execute(text(f"CREATE TABLE {table} ({columns})"))
        seed_name, seed_en, seed_desc, seed_desc_en = migration.MEALS[0]
        connection.execute(
            text("INSERT INTO meals VALUES (:id, :name, :description, :price, :available)"),
            [
                {
                    "id": "original",
                    "name": seed_name,
                    "description": "Edited by admin",
                    "price": 333,
                    "available": False,
                },
                {
                    "id": "custom",
                    "name": "Custom meal",
                    "description": "Custom description",
                    "price": 222,
                    "available": True,
                },
                {
                    "id": "english",
                    "name": migration.MEALS[1][1],
                    "description": migration.MEALS[1][3],
                    "price": 444,
                    "available": False,
                },
            ],
        )
        connection.execute(text("INSERT INTO order_items VALUES (:name)"), {"name": seed_name})
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        rows = {
            row["id"]: row for row in connection.execute(text("SELECT * FROM meals")).mappings()
        }
        assert rows["original"]["name_en"] == seed_en
        assert rows["original"]["description"] == "Edited by admin"
        assert rows["original"]["description_en"] is None
        assert rows["original"]["price_nok"] == 333
        assert rows["original"]["available"] == 0
        assert rows["custom"]["name_en"] is None
        assert rows["custom"]["description"] == "Custom description"
        assert rows["english"]["name"] == migration.MEALS[1][0]
        assert rows["english"]["price_nok"] == 444
        item = connection.execute(text("SELECT * FROM order_items")).mappings().one()
        assert item["meal_name"] == seed_name
        assert item["meal_name_en"] == seed_en
    engine.dispose()
