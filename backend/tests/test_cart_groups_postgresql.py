"""Real cart serialization checks in an isolated disposable PostgreSQL schema."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from prepwise_api.models import Base, CartItem, Meal, Order, OrderStatus, PickupLocation, User
from prepwise_api.schemas.cart import CartGroupWrite
from prepwise_api.services import ApplicationConflictError
from prepwise_api.services.cart import add_user_cart_item, get_user_cart, write_user_cart_group
from prepwise_api.services.orders import cancel_user_order, create_user_order
from prepwise_api.services.pickup_schedule import list_pickup_options


@pytest.fixture
def group_database() -> Iterator[tuple[Engine, UUID, UUID, UUID]]:
    value = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL for local PostgreSQL group/race checks")
    url = make_url(value)
    assert url.host in {"127.0.0.1", "localhost"} and url.drivername.startswith("postgresql")
    assert url.database and (
        url.database.endswith(("_test", "_ci")) or url.database == "prepwise_round1"
    )
    schema = "cart_group_test_" + uuid4().hex
    base_engine = create_engine(url, connect_args={"connect_timeout": 5})
    with base_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = base_engine.execution_options(schema_translate_map={None: schema})
    # No vector extension or external embeddings are needed by these domain tests.
    tables = [table for table in Base.metadata.sorted_tables if table.name != "knowledge_chunks"]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        user = User(external_subject="group-concurrency-customer")
        meal = Meal(
            name="Concurrency meal",
            description="Local test",
            price_nok=Decimal("25"),
            calories=100,
            protein_grams=Decimal("10"),
            carbohydrate_grams=Decimal("5"),
            fat_grams=Decimal("2"),
        )
        location = PickupLocation(
            name="Concurrency pickup", address_line="Test", postal_code="0000", city="Oslo"
        )
        session.add_all([user, meal, location])
        session.commit()
        ids = user.id, meal.id, location.id
    try:
        yield engine, *ids
    finally:
        assert schema.startswith("cart_group_test_") and len(schema) == 48
        with base_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base_engine.dispose()


def test_concurrent_adds_refresh_stale_identity_maps(
    group_database: tuple[Engine, UUID, UUID, UUID],
) -> None:
    engine, user_id, meal_id, _ = group_database
    with Session(engine) as session:
        item_id = add_user_cart_item(session, user_id, meal_id, 1).items[0].id
    barrier = Barrier(6)

    def add(_: int) -> None:
        with Session(engine) as session:
            stale_item = session.get(CartItem, item_id)
            assert stale_item and stale_item.quantity == 1
            barrier.wait(timeout=10)
            add_user_cart_item(session, user_id, meal_id, 1)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(add, range(6)))
    with Session(engine) as session:
        assert get_user_cart(session, user_id).total_quantity == 7


def test_concurrent_checkout_creates_exactly_one_group_order(
    group_database: tuple[Engine, UUID, UUID, UUID],
) -> None:
    engine, user_id, meal_id, location_id = group_database
    day = list_pickup_options().days[0]
    with Session(engine) as session:
        group_id = (
            write_user_cart_group(
                session,
                user_id,
                CartGroupWrite(
                    pickup_location_id=location_id, pickup_date=day.date, pickup_slot="16-18"
                ),
            )
            .groups[0]
            .id
        )
        add_user_cart_item(session, user_id, meal_id, 1, group_id=group_id)
        add_user_cart_item(session, user_id, meal_id, 2)
    barrier = Barrier(2)

    def checkout(_: int) -> bool:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                create_user_order(
                    session,
                    user_id,
                    location_id,
                    pickup_date=day.date,
                    pickup_slot="16-18",
                    group_id=group_id,
                )
            except ApplicationConflictError:
                return False
            return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(checkout, range(2))) == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        cart = get_user_cart(session, user_id)
        assert cart.total_quantity == 2 and cart.items[0].group_id is None


def test_cancellation_refreshes_admin_completed_status(
    group_database: tuple[Engine, UUID, UUID, UUID],
) -> None:
    engine, user_id, meal_id, location_id = group_database
    day = list_pickup_options().days[0]
    with Session(engine) as session:
        add_user_cart_item(session, user_id, meal_id, 1)
        order_id = create_user_order(
            session, user_id, location_id, pickup_date=day.date, pickup_slot="16-18"
        ).id
    loaded, completed = Event(), Event()

    def cancel() -> bool:
        with Session(engine) as session:
            stale_order = session.get(Order, order_id)
            assert stale_order and stale_order.status == OrderStatus.RECEIVED
            loaded.set()
            assert completed.wait(timeout=10)
            try:
                cancel_user_order(session, user_id, order_id)
            except ApplicationConflictError:
                return False
            return True

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(cancel)
        assert loaded.wait(timeout=10)
        with Session(engine) as session:
            order = session.scalar(select(Order).where(Order.id == order_id).with_for_update())
            assert order is not None
            order.status = OrderStatus.COMPLETED
            session.commit()
        completed.set()
        assert pending.result(timeout=10) is False
    with Session(engine) as session:
        assert session.get(Order, order_id).status == OrderStatus.COMPLETED  # type: ignore[union-attr]
