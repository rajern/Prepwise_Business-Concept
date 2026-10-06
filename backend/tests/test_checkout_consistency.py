"""Real HTTP review, optimistic update, and checkout replay regressions."""

from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_orders_api import (
    _first_meal_and_location,
    _headers,
    _pickup,
    client_and_engine,
)

from prepwise_api.models import CartGroup, CartItem, Meal, Order, OrderItem, PickupLocation
from prepwise_api.services import ApplicationConflictError
from prepwise_api.services import orders as order_service

__all__ = ["client_and_engine"]


def _reviewed_checkout(
    client: TestClient, engine: Engine, *, token: str = "valid-token"
) -> tuple[dict[str, object], dict[str, object]]:
    meal, location = _first_meal_and_location(engine)
    added = client.post(
        "/api/cart/items", headers=_headers(token), json={"meal_id": str(meal.id), "quantity": 2}
    )
    assert added.status_code == 201
    selection = {"pickup_location_id": str(location.id), **_pickup(client), "group_id": None}
    review = client.post("/api/orders/review", headers=_headers(token), json=selection)
    assert review.status_code == 200
    snapshot = cast(dict[str, object], review.json())
    payload = {
        **selection,
        "review_fingerprint": snapshot["review_fingerprint"],
        "idempotency_key": str(uuid4()),
    }
    return payload, snapshot


def test_review_is_read_only_and_returns_authoritative_total(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _, snapshot = _reviewed_checkout(client, engine)
    cart = client.get("/api/cart", headers=_headers()).json()
    assert snapshot["total_nok"] == cart["total_nok"]
    assert snapshot["total_quantity"] == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 0
        assert session.scalar(select(func.count()).select_from(CartGroup)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1


def test_checkout_rejection_proves_absence_only_after_key_lookup(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    with Session(engine) as session:
        item = session.scalar(select(CartItem))
        assert item is not None
        meal = session.get(Meal, item.meal_id)
        assert meal is not None
        meal.price_nok += Decimal("10.00")
        session.commit()
    rejected = client.post("/api/orders", headers=_headers(), json=payload)
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "checkout_not_created"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
    # A failed authentication cannot establish whether an earlier attempt committed.
    unauthenticated = client.post("/api/orders", json=payload)
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] != "checkout_not_created"
    selection = {
        field: payload[field]
        for field in ("pickup_location_id", "pickup_date", "pickup_slot", "group_id")
    }
    refreshed = client.post("/api/orders/review", headers=_headers(), json=selection).json()
    payload["review_fingerprint"] = refreshed["review_fingerprint"]
    assert client.post("/api/orders", headers=_headers(), json=payload).status_code == 201
    payload["review_fingerprint"] = "0" * 64
    mismatch = client.post("/api/orders", headers=_headers(), json=payload)
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "conflict"


@pytest.mark.parametrize("change", ["location-name", "location-address", "meal-name"])
def test_assistant_confirmation_binds_reviewed_location_and_names(
    client_and_engine: tuple[TestClient, Engine], change: str
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    location_id = UUID(str(payload["pickup_location_id"]))
    with Session(engine) as session:
        item = session.scalar(select(CartItem))
        assert item is not None
        user_id = item.user_id
        prepared = order_service.prepare_user_order_confirmation(
            session,
            user_id,
            location_id,
            "prepare-request",
            pickup_date=date.fromisoformat(str(payload["pickup_date"])),
            pickup_slot="16-18",
        )
    with Session(engine) as session:
        location = session.get(PickupLocation, location_id)
        item = session.scalar(select(CartItem))
        assert location is not None and item is not None
        if change == "location-name":
            location.name = "Changed pickup"
        elif change == "location-address":
            location.address_line = "Different street"
        else:
            meal = session.get(Meal, item.meal_id)
            assert meal is not None
            meal.name = "Changed meal"
        session.commit()
    with Session(engine) as session:
        with pytest.raises(ApplicationConflictError, match="changed after preparation"):
            order_service.confirm_user_order(
                session,
                user_id,
                UUID(str(prepared["confirmation_token"])),
                "confirm-request",
                str(prepared["confirmation_phrase"]),
            )
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1


@pytest.mark.parametrize(
    "change",
    ["price", "quantity", "meal-name", "translation", "location-name", "address", "availability"],
)
def test_checkout_rejects_changed_review_without_consuming_cart(
    client_and_engine: tuple[TestClient, Engine], change: str
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    with Session(engine) as session:
        item = session.scalar(select(CartItem))
        assert item is not None
        meal = session.get(Meal, item.meal_id)
        location = session.get(PickupLocation, UUID(str(payload["pickup_location_id"])))
        assert meal is not None and location is not None
        if change == "price":
            meal.price_nok += Decimal("50.00")
        elif change == "quantity":
            item.quantity += 1
        elif change == "meal-name":
            meal.name = "Changed meal"
        elif change == "translation":
            meal.name_en = "Changed English name"
        elif change == "location-name":
            location.name = "Different pickup"
        elif change == "address":
            location.address_line = "Different street"
        else:
            meal.available = False
        session.commit()
    result = client.post("/api/orders", headers=_headers(), json=payload)
    assert result.status_code == 409
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1


def test_successful_checkout_replay_returns_original_and_preserves_later_cart(
    client_and_engine: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = client_and_engine
    payload, snapshot = _reviewed_checkout(client, engine)
    first = client.post("/api/orders", headers=_headers(), json=payload)
    assert first.status_code == 201
    meal, _ = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 3}
    )

    def expired_selection(*args: object, **kwargs: object) -> tuple[object, object]:
        raise AssertionError("A committed replay must not revalidate today's pickup options")

    monkeypatch.setattr(order_service, "validate_pickup_selection", expired_selection)
    replay = client.post("/api/orders", headers=_headers(), json=payload)
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["total_nok"] == snapshot["total_nok"]
    assert client.get("/api/cart", headers=_headers()).json()["total_quantity"] == 3
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 1


def test_checkout_key_conflict_rejects_changed_payload(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    assert client.post("/api/orders", headers=_headers(), json=payload).status_code == 201
    changed = {**payload, "pickup_slot": "18-20"}
    assert client.post("/api/orders", headers=_headers(), json=changed).status_code == 409
    forged = {**payload, "review_fingerprint": "0" * 64}
    assert client.post("/api/orders", headers=_headers(), json=forged).status_code == 409


def test_checkout_rejects_replaced_line_and_changed_named_group_selection(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    meal, location = _first_meal_and_location(engine)
    item = client.get("/api/cart", headers=_headers()).json()["items"][0]
    assert client.delete(f"/api/cart/items/{item['id']}", headers=_headers()).status_code == 204
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 2}
    )
    assert client.post("/api/orders", headers=_headers(), json=payload).status_code == 409
    selection = {"pickup_location_id": str(location.id), **_pickup(client)}
    group = client.post("/api/cart/groups", headers=_headers(), json=selection).json()["groups"][0]
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1, "group_id": group["id"]},
    )
    selection["group_id"] = group["id"]
    review = client.post("/api/orders/review", headers=_headers(), json=selection).json()
    assert (
        client.patch(
            f"/api/cart/groups/{group['id']}",
            headers=_headers(),
            json={"pickup_slot": "18-20", "expected_version": group["version"]},
        ).status_code
        == 200
    )
    changed = {
        **selection,
        "review_fingerprint": review["review_fingerprint"],
        "idempotency_key": str(uuid4()),
    }
    assert client.post("/api/orders", headers=_headers(), json=changed).status_code == 409
    assert client.get("/api/cart", headers=_headers()).json()["total_quantity"] == 3


def test_checkout_keys_and_reviews_are_user_scoped(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    other_payload, _ = _reviewed_checkout(client, engine, token="other-token")
    first = client.post("/api/orders", headers=_headers(), json=payload)
    assert first.status_code == 201
    assert (
        client.post("/api/orders", headers=_headers("other-token"), json=payload).status_code == 409
    )
    other_payload["idempotency_key"] = payload["idempotency_key"]
    second = client.post("/api/orders", headers=_headers("other-token"), json=other_payload)
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 2


def test_unassigned_checkout_is_atomic_and_preserves_named_groups(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    meal, _ = _first_meal_and_location(engine)
    group = client.post("/api/cart/groups", headers=_headers(), json={}).json()["groups"][0]
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 4, "group_id": group["id"]},
    )
    result = client.post("/api/orders", headers=_headers(), json=payload)
    assert result.status_code == 201
    assert result.json()["items"][0]["quantity"] == 2
    cart = client.get("/api/cart", headers=_headers()).json()
    assert cart["total_quantity"] == 4
    assert cart["items"][0]["group_id"] == group["id"]
    assert len(cart["groups"]) == 1


def test_checkout_failure_rolls_back_order_key_and_cart_deletion(
    client_and_engine: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = client_and_engine
    payload, _ = _reviewed_checkout(client, engine)
    original = order_service._create_order_from_checkout_state

    def fail_after_writes(*args: object, **kwargs: object) -> UUID:
        original(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("simulated failure before commit")

    monkeypatch.setattr(order_service, "_create_order_from_checkout_state", fail_after_writes)
    with pytest.raises(RuntimeError, match="simulated failure before commit"):
        client.post("/api/orders", headers=_headers(), json=payload)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1
    monkeypatch.setattr(order_service, "_create_order_from_checkout_state", original)
    assert client.post("/api/orders", headers=_headers(), json=payload).status_code == 201


def test_stale_quantity_and_moves_never_overwrite_newer_changes(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, _ = _first_meal_and_location(engine)
    item = client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    ).json()["items"][0]
    client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 2}
    )
    stale = {"quantity": 2, "expected_quantity": 1, "expected_group_id": None}
    assert (
        client.patch(f"/api/cart/items/{item['id']}", headers=_headers(), json=stale).status_code
        == 409
    )
    assert client.get("/api/cart", headers=_headers()).json()["total_quantity"] == 3
    group = client.post("/api/cart/groups", headers=_headers(), json={}).json()["groups"][0]
    move = {
        "quantity": 3,
        "group_id": group["id"],
        "expected_quantity": 3,
        "expected_group_id": None,
    }
    assert (
        client.patch(f"/api/cart/items/{item['id']}", headers=_headers(), json=move).status_code
        == 200
    )
    old_group = {"quantity": 2, "expected_quantity": 3, "expected_group_id": None}
    assert (
        client.patch(
            f"/api/cart/items/{item['id']}", headers=_headers(), json=old_group
        ).status_code
        == 409
    )
    current = client.get("/api/cart", headers=_headers()).json()["items"][0]
    assert current["quantity"] == 3 and current["group_id"] == group["id"]


def test_http_updates_require_expected_state_and_group_selection_rejects_stale_version(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    item = client.post(
        "/api/cart/items", headers=_headers(), json={"meal_id": str(meal.id), "quantity": 1}
    ).json()["items"][0]
    assert (
        client.patch(
            f"/api/cart/items/{item['id']}", headers=_headers(), json={"quantity": 2}
        ).status_code
        == 422
    )
    group = client.post("/api/cart/groups", headers=_headers(), json={}).json()["groups"][0]
    update = {"pickup_location_id": str(location.id), "expected_version": group["version"]}
    assert (
        client.patch(f"/api/cart/groups/{group['id']}", headers=_headers(), json={}).status_code
        == 422
    )
    first = client.patch(f"/api/cart/groups/{group['id']}", headers=_headers(), json=update)
    assert first.status_code == 200
    updated = first.json()["groups"][0]
    assert updated["version"] != group["version"]
    stale = {"pickup_location_id": None, "expected_version": group["version"]}
    assert (
        client.patch(f"/api/cart/groups/{group['id']}", headers=_headers(), json=stale).status_code
        == 409
    )
    assert client.get("/api/cart", headers=_headers()).json()["groups"][0] == updated
