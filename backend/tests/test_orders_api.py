from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.auth import (
    AccessTokenClaims,
    InvalidAccessTokenError,
    get_access_token_validator,
)
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base, CartItem, Meal, Order, OrderItem, PickupLocation
from prepwise_api.seed import seed_database


class StubAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        object_ids = {
            "valid-token": "d074c8a4-4494-4597-9d33-2df93b5f9959",
            "other-token": "52a8cd26-8b95-447b-aa0f-80efeb1aa218",
        }
        object_id = object_ids.get(token)
        if object_id is None:
            raise InvalidAccessTokenError
        return AccessTokenClaims(
            tenant_id="1a782388-bf90-4ea8-af8f-bcc755f5cd7e",
            object_id=object_id,
            subject="pairwise-subject",
            email=f"{object_id}@example.com",
            display_name="Prepwise Customer",
        )


@pytest.fixture
def client_and_engine() -> Iterator[tuple[TestClient, Engine]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_database(engine)

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_access_token_validator] = StubAccessTokenValidator
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _headers(token: str = "valid-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pickup(client: TestClient) -> dict[str, str]:
    day = client.get("/api/pickup-locations/options").json()["days"][0]
    return {"pickup_date": day["date"], "pickup_slot": "16-18"}


def _first_meal_and_location(engine: Engine) -> tuple[Meal, PickupLocation]:
    with Session(engine) as session:
        meal = session.scalar(select(Meal).order_by(Meal.name))
        location = session.scalar(select(PickupLocation).order_by(PickupLocation.name))
        assert meal is not None
        assert location is not None
        session.expunge(meal)
        session.expunge(location)
        return meal, location


def test_checkout_creates_historical_order_and_clears_cart_atomically(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    add_response = client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 2},
    )
    assert add_response.status_code == 201

    checkout_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    )

    assert checkout_response.status_code == 201
    order = checkout_response.json()
    assert order["status"] == "received"
    assert order["total_nok"] == str(meal.price_nok * 2)
    assert order["pickup_location_name"] == location.name
    assert order["items"] == [
        {
            "meal_id": str(meal.id),
            "meal_name": meal.name,
            "quantity": 2,
            "unit_price_nok": str(meal.price_nok),
            "line_total_nok": str(meal.price_nok * 2),
        }
    ]
    assert client.get("/api/cart", headers=_headers()).json()["items"] == []

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 1
        assert session.scalar(select(func.count()).select_from(CartItem)) == 0
        persisted_meal = session.get(Meal, meal.id)
        assert persisted_meal is not None
        persisted_meal.price_nok = Decimal("999.00")
        session.commit()

    detail_response = client.get(f"/api/orders/{order['id']}", headers=_headers())
    assert detail_response.status_code == 200
    assert detail_response.json()["items"][0]["unit_price_nok"] == str(meal.price_nok)


def test_order_history_is_scoped_to_the_authenticated_user(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )
    created = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    ).json()

    history_response = client.get("/api/orders", headers=_headers())
    assert history_response.status_code == 200
    assert [order["id"] for order in history_response.json()] == [created["id"]]

    assert client.get("/api/orders", headers=_headers("other-token")).json() == []
    other_detail_response = client.get(
        f"/api/orders/{created['id']}",
        headers=_headers("other-token"),
    )
    assert other_detail_response.status_code == 404


@pytest.mark.parametrize("failure", ["inactive-location", "unavailable-meal"])
def test_failed_checkout_preserves_cart_and_creates_no_partial_order(
    client_and_engine: tuple[TestClient, Engine],
    failure: str,
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )

    with Session(engine) as session:
        if failure == "inactive-location":
            persisted_location = session.get(PickupLocation, location.id)
            assert persisted_location is not None
            persisted_location.active = False
        else:
            persisted_meal = session.get(Meal, meal.id)
            assert persisted_meal is not None
            persisted_meal.available = False
        session.commit()

    response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    )

    assert response.status_code == 409
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1


def test_checkout_rejects_empty_cart_and_frontend_supplied_price(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _, location = _first_meal_and_location(engine)

    empty_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    )
    assert empty_response.status_code == 409

    untrusted_price_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), "total_nok": "1.00", **_pickup(client)},
    )
    assert untrusted_price_response.status_code == 422


def test_checkout_requires_explicit_selection_and_preserves_cart_on_invalid_date(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    )
    missing = client.post(
        "/api/orders", headers=_headers(), json={"pickup_location_id": str(location.id)}
    )
    assert missing.status_code == 422
    invalid = client.post(
        "/api/orders",
        headers=_headers(),
        json={
            "pickup_location_id": str(location.id),
            "pickup_date": "2020-01-01",
            "pickup_slot": "16-18",
        },
    )
    assert invalid.status_code == 422
    assert client.get("/api/cart", headers=_headers()).json()["total_quantity"] == 1


def test_checkout_stores_selected_window_and_historical_translation(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    from datetime import datetime

    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    cart = client.post(
        "/api/cart/items?lang=en", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    ).json()
    assert cart["items"][0]["meal"]["name"] == meal.name_en
    day = client.get("/api/pickup-locations/options").json()["days"][-1]
    slot = day["slots"][-1]
    result = client.post(
        "/api/orders?lang=en",
        headers=_headers(),
        json={
            "pickup_location_id": str(location.id),
            "pickup_date": day["date"],
            "pickup_slot": slot["id"],
        },
    )
    assert result.status_code == 201
    order = result.json()
    # SQLite returns naive UTC datetimes; compare the persisted UTC instant explicitly.
    expected = datetime.fromisoformat(slot["start_at"]).timestamp()
    from datetime import UTC

    actual = datetime.fromisoformat(order["pickup_start_at"])
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=UTC)
    assert actual.timestamp() == expected
    with Session(engine) as session:
        persisted = session.get(Meal, meal.id)
        assert persisted is not None
        persisted.name_en = "Changed translation"
        session.commit()
    historical = client.get(f"/api/orders/{order['id']}?lang=en", headers=_headers()).json()
    assert historical["items"][0]["meal_name"] == meal.name_en


def test_group_checkout_consumes_only_selected_group_and_checks_saved_pickup(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    day = client.get("/api/pickup-locations/options").json()["days"][1]
    pickup = {
        "pickup_location_id": str(location.id),
        "pickup_date": day["date"],
        "pickup_slot": "18-20",
    }
    groups: list[dict[str, str]] = []
    for _ in range(2):
        response_groups = client.post("/api/cart/groups", headers=_headers(), json=pickup).json()[
            "groups"
        ]
        group = next(
            group
            for group in response_groups
            if group["id"] not in {existing["id"] for existing in groups}
        )
        groups.append(group)
        assert (
            client.post(
                "/api/cart/items",
                headers=_headers(),
                json={"meal_id": str(meal.id), "quantity": 1, "group_id": group["id"]},
            ).status_code
            == 201
        )
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    )
    # Old clients/assistant cannot accidentally combine all dates.
    assert client.post("/api/orders", headers=_headers(), json=pickup).status_code == 409
    stale = client.post(
        "/api/orders",
        headers=_headers(),
        json={**pickup, "pickup_slot": "16-18", "group_id": groups[0]["id"]},
    )
    assert stale.status_code == 409
    other = client.post(
        "/api/orders", headers=_headers("other-token"), json={**pickup, "group_id": groups[0]["id"]}
    )
    assert other.status_code == 404
    created = client.post(
        "/api/orders", headers=_headers(), json={**pickup, "group_id": groups[0]["id"]}
    )
    assert created.status_code == 201
    assert len(created.json()["items"]) == 1
    assert created.json()["can_cancel"] is True
    remaining = client.get("/api/cart", headers=_headers()).json()
    assert remaining["total_quantity"] == 2
    assert {item["group_id"] for item in remaining["items"]} == {None, groups[1]["id"]}


def test_customer_cancellation_preserves_history_and_is_terminal(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    )
    order = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    ).json()
    assert (
        client.post(
            f"/api/orders/{order['id']}/cancel", headers=_headers("other-token")
        ).status_code
        == 404
    )
    cancelled = client.post(f"/api/orders/{order['id']}/cancel", headers=_headers())
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["can_cancel"] is False
    assert cancelled.json()["items"] == order["items"]
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=_headers()).status_code == 409
    assert client.get("/api/orders", headers=_headers()).json()[0]["status"] == "cancelled"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 1


def test_customer_cannot_cancel_on_pickup_day(client_and_engine: tuple[TestClient, Engine]) -> None:
    from datetime import UTC, datetime

    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    )
    order = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), **_pickup(client)},
    ).json()
    with Session(engine) as session:
        saved = session.scalar(select(Order))
        assert saved is not None
        saved.pickup_start_at = datetime.now(UTC)
        session.commit()
    assert (
        client.get(f"/api/orders/{order['id']}", headers=_headers()).json()["can_cancel"] is False
    )
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=_headers()).status_code == 409


@pytest.mark.parametrize(
    "pickup_day,expected_deadline",
    [
        ("2026-03-29", "2026-03-28T23:00:00+00:00"),
        ("2026-10-25", "2026-10-24T22:00:00+00:00"),
        ("2026-10-26", "2026-10-25T23:00:00+00:00"),
    ],
)
def test_cancellation_deadline_uses_oslo_calendar_midnight(
    pickup_day: str, expected_deadline: str
) -> None:
    from datetime import date, datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from prepwise_api.models import OrderStatus
    from prepwise_api.services.orders import can_cancel_order, cancellation_deadline

    order = Order(
        status=OrderStatus.RECEIVED,
        pickup_start_at=datetime.combine(
            date.fromisoformat(pickup_day), time(16), ZoneInfo("Europe/Oslo")
        ),
    )
    deadline = cancellation_deadline(order)
    assert deadline == datetime.fromisoformat(expected_deadline)
    assert can_cancel_order(order, now=deadline - timedelta(microseconds=1))
    assert not can_cancel_order(order, now=deadline)
    assert not can_cancel_order(order, now=deadline + timedelta(hours=1))


def test_assistant_confirmation_cannot_ignore_new_pickup_groups(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    from datetime import date
    from uuid import UUID

    from prepwise_api.services import ApplicationConflictError
    from prepwise_api.services.orders import confirm_user_order, prepare_user_order_confirmation

    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    pickup = _pickup(client)
    cart = client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    ).json()
    with Session(engine) as session:
        item = session.scalar(select(CartItem))
        assert item is not None
        user_id = item.user_id
        prepared = prepare_user_order_confirmation(
            session,
            user_id,
            location.id,
            "prepare",
            pickup_date=date.fromisoformat(pickup["pickup_date"]),
            pickup_slot="16-18",
        )
    group_id = client.post("/api/cart/groups", headers=_headers(), json={}).json()["groups"][0][
        "id"
    ]
    client.patch(
        f"/api/cart/items/{cart['items'][0]['id']}",
        headers=_headers(),
        json={"quantity": 1, "group_id": group_id},
    )
    with Session(engine) as session:
        with pytest.raises(ApplicationConflictError, match="separate pickup groups"):
            confirm_user_order(
                session,
                user_id,
                UUID(str(prepared["confirmation_token"])),
                "confirm",
                str(prepared["confirmation_phrase"]),
            )
        assert session.scalar(select(func.count()).select_from(Order)) == 0
