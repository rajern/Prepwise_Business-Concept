"""Optional transaction smoke against the isolated round-one PostgreSQL database."""

import os
from collections.abc import Iterator
from datetime import UTC
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from prepwise_api.models import Meal, Order, PickupLocation, User
from prepwise_api.services import ApplicationConflictError, ApplicationValidationError
from prepwise_api.services.cart import add_user_cart_item, get_user_cart
from prepwise_api.services.orders import (
    confirm_user_order,
    create_user_order,
    prepare_user_order_confirmation,
)
from prepwise_api.services.pickup_schedule import list_pickup_options


@pytest.fixture
def postgres_session() -> Iterator[Session]:
    value = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL for isolated PostgreSQL product verification")
    url = make_url(value)
    assert url.host in {"127.0.0.1", "localhost"}
    assert url.drivername.startswith("postgresql")
    assert url.database is not None and (
        url.database.endswith("_ci")
        or url.database.endswith("_test")
        or url.database == "prepwise_round1"
    ), "Product integration tests require an explicitly named disposable test database"
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        # Service commits release savepoints; the outer rollback leaves the demo data untouched.
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()
    engine.dispose()


def _checkout_entities(session: Session) -> tuple[User, Meal, PickupLocation]:
    suffix = str(uuid4())
    user = User(external_subject=f"product-smoke:{suffix}")
    meal = Meal(
        name=f"Norsk testmåltid {suffix}",
        name_en=f"English test meal {suffix}",
        description="Norsk testbeskrivelse.",
        description_en="English test description.",
        price_nok=Decimal("25.00"),
        calories=100,
        protein_grams=Decimal("10.00"),
        carbohydrate_grams=Decimal("5.00"),
        fat_grams=Decimal("4.00"),
        available=True,
    )
    location = PickupLocation(
        name=f"Test pickup {suffix}",
        address_line="Test address",
        postal_code="0000",
        city="Oslo",
    )
    session.add_all([user, meal, location])
    session.commit()
    return user, meal, location


def test_postgres_checkout_and_confirmation_preserve_explicit_windows(
    postgres_session: Session,
) -> None:
    session = postgres_session
    user, meal, location = _checkout_entities(session)
    day = list_pickup_options().days[4]
    slot = day.slots[1]
    added = add_user_cart_item(session, user.id, meal.id, 2, lang="en")
    assert added.items[0].meal.name == meal.name_en
    with pytest.raises(ApplicationValidationError):
        create_user_order(
            session,
            user.id,
            location.id,
            pickup_date=day.date,
            pickup_slot="invalid",  # type: ignore[arg-type]
        )
    assert get_user_cart(session, user.id).total_quantity == 2
    order = create_user_order(
        session,
        user.id,
        location.id,
        pickup_date=day.date,
        pickup_slot="18-20",
        lang="en",
    )
    assert order.pickup_start_at == slot.start_at.astimezone(UTC)
    assert order.pickup_end_at == slot.end_at.astimezone(UTC)
    assert order.items[0].meal_name == meal.name_en
    assert get_user_cart(session, user.id).total_quantity == 0
    add_user_cart_item(session, user.id, meal.id, 1)
    prepared = prepare_user_order_confirmation(
        session,
        user.id,
        location.id,
        "prepare-request",
        pickup_date=day.date,
        pickup_slot="18-20",
    )
    token = UUID(str(prepared["confirmation_token"]))
    confirmed = confirm_user_order(
        session,
        user.id,
        token,
        "confirm-request",
        str(prepared["confirmation_phrase"]),
        lang="en",
    )
    assert confirmed.pickup_start_at == order.pickup_start_at
    assert confirmed.pickup_end_at == order.pickup_end_at
    with pytest.raises(ApplicationConflictError, match="already been used"):
        confirm_user_order(
            session,
            user.id,
            token,
            "repeat-request",
            str(prepared["confirmation_phrase"]),
        )
    assert (
        session.scalar(select(func.count()).select_from(Order).where(Order.user_id == user.id)) == 2
    )


def test_postgres_confirmation_rejects_cart_changed_after_review(
    postgres_session: Session,
) -> None:
    session = postgres_session
    user, meal, location = _checkout_entities(session)
    day = list_pickup_options().days[0]
    add_user_cart_item(session, user.id, meal.id, 1)
    prepared = prepare_user_order_confirmation(
        session,
        user.id,
        location.id,
        "prepare-request",
        pickup_date=day.date,
        pickup_slot="16-18",
    )
    add_user_cart_item(session, user.id, meal.id, 1)
    with pytest.raises(ApplicationConflictError, match="Cart changed"):
        confirm_user_order(
            session,
            user.id,
            UUID(str(prepared["confirmation_token"])),
            "confirm-request",
            str(prepared["confirmation_phrase"]),
        )
    assert get_user_cart(session, user.id).total_quantity == 2
    assert (
        session.scalar(select(func.count()).select_from(Order).where(Order.user_id == user.id)) == 0
    )
