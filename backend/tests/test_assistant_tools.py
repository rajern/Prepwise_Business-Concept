import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.assistant_tools import (
    AssistantToolContext,
    AssistantToolOperation,
    AssistantToolRegistry,
)
from prepwise_api.models import Base, Meal, Order, OrderConfirmation, PickupLocation, User
from prepwise_api.seed import seed_database


@pytest.fixture
def engine() -> Iterator[Engine]:
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    seed_database(test_engine)
    with Session(test_engine) as session:
        session.add_all(
            [
                User(
                    external_subject="tool-user-a",
                    email="tool-user-a@example.com",
                    display_name="Tool User A",
                ),
                User(
                    external_subject="tool-user-b",
                    email="tool-user-b@example.com",
                    display_name="Tool User B",
                ),
            ]
        )
        session.commit()
    try:
        yield test_engine
    finally:
        test_engine.dispose()


def _result_payload(result_json: str) -> dict[str, object]:
    payload = json.loads(result_json)
    assert isinstance(payload, dict)
    return payload


def _user(session: Session, external_subject: str) -> User:
    user = session.scalar(select(User).where(User.external_subject == external_subject))
    assert user is not None
    return user


def test_tool_definitions_are_explicit_and_do_not_accept_user_identity() -> None:
    definitions = AssistantToolRegistry().definitions()

    assert {definition["name"] for definition in definitions} == {
        "search_meals",
        "get_meal_details",
        "get_cart",
        "add_to_cart",
        "remove_from_cart",
        "get_user_orders",
        "get_pickup_locations",
        "prepare_order",
        "create_order",
    }
    for definition in definitions:
        assert definition["strict"] is True
        parameters = definition["parameters"]
        assert isinstance(parameters, dict)
        assert parameters["additionalProperties"] is False
        properties = parameters.get("properties", {})
        assert isinstance(properties, dict)
        assert set(parameters["required"]) == set(properties)
        assert "user_id" not in properties

    registry = AssistantToolRegistry()
    assert registry.operation("search_meals") is AssistantToolOperation.READ
    assert registry.operation("get_cart") is AssistantToolOperation.READ
    assert registry.operation("add_to_cart") is AssistantToolOperation.WRITE
    assert registry.operation("prepare_order") is AssistantToolOperation.WRITE
    assert registry.operation("create_order") is AssistantToolOperation.WRITE
    descriptions: dict[str, str] = {}
    for definition in definitions:
        name = definition["name"]
        description = definition["description"]
        assert isinstance(name, str)
        assert isinstance(description, str)
        descriptions[name] = description
    assert all(
        str(descriptions[name]).startswith(f"{registry.operation(name).value.upper()}:")
        for name in descriptions
    )


def test_search_meals_applies_nutrition_text_and_result_limit(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        context = AssistantToolContext(session=session, user=_user(session, "tool-user-a"))
        result = _result_payload(
            registry.execute_json(
                "search_meals",
                {
                    "query": "kylling",
                    "min_protein_grams": "30",
                    "max_calories": 800,
                    "limit": 2,
                },
                context,
            )
        )

    assert result["ok"] is True
    data = result["data"]
    assert isinstance(data, list)
    assert 0 < len(data) <= 2
    assert all(isinstance(meal, dict) for meal in data)
    assert all(Decimal(meal["protein_grams"]) >= 30 for meal in data)
    assert all(meal["calories"] <= 800 for meal in data)
    assert all(
        "kylling" in " ".join([meal["name"], meal["description"], *meal["ingredients"]]).casefold()
        for meal in data
    )


def test_cart_tools_preserve_authenticated_user_scope(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        meal_id = session.scalar(select(Meal.id).order_by(Meal.name))
        assert meal_id is not None
        user_a = _user(session, "tool-user-a")
        user_b = _user(session, "tool-user-b")

        added = _result_payload(
            registry.execute_json(
                "add_to_cart",
                {"meal_id": str(meal_id), "quantity": 2},
                AssistantToolContext(session=session, user=user_a),
            )
        )
        assert added["ok"] is True
        added_data = added["data"]
        assert isinstance(added_data, dict)
        added_items = added_data["items"]
        assert isinstance(added_items, list)
        assert len(added_items) == 1
        assert isinstance(added_items[0], dict)
        item_id = added_items[0]["id"]

        other_cart = _result_payload(
            registry.execute_json(
                "get_cart",
                {},
                AssistantToolContext(session=session, user=user_b),
            )
        )
        assert isinstance(other_cart["data"], dict)
        assert other_cart["data"]["items"] == []

        cross_user_remove = _result_payload(
            registry.execute_json(
                "remove_from_cart",
                {"cart_item_id": item_id},
                AssistantToolContext(session=session, user=user_b),
            )
        )
        assert cross_user_remove["ok"] is False
        assert isinstance(cross_user_remove["error"], dict)
        assert cross_user_remove["error"]["code"] == "not_found"

        removed = _result_payload(
            registry.execute_json(
                "remove_from_cart",
                {"cart_item_id": item_id},
                AssistantToolContext(session=session, user=user_a),
            )
        )
        assert removed["ok"] is True
        assert isinstance(removed["data"], dict)
        assert removed["data"]["items"] == []


def test_tool_arguments_use_existing_validation_and_safe_errors(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        meal_id = session.scalar(select(Meal.id).order_by(Meal.name))
        assert meal_id is not None
        context = AssistantToolContext(session=session, user=_user(session, "tool-user-a"))

        invalid = _result_payload(
            registry.execute_json(
                "add_to_cart",
                {"meal_id": str(meal_id), "quantity": 0},
                context,
            )
        )
        unknown = _result_payload(registry.execute_json("delete_account", {}, context))

    assert invalid["ok"] is False
    assert isinstance(invalid["error"], dict)
    assert invalid["error"]["code"] == "invalid_tool_arguments"
    assert unknown == {
        "ok": False,
        "error": {
            "code": "invalid_tool_arguments",
            "message": "Unknown tool: delete_account",
            "details": [],
        },
    }


def test_order_and_pickup_tools_return_only_allowed_rows(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        user_a = _user(session, "tool-user-a")
        user_b = _user(session, "tool-user-b")
        locations = session.scalars(select(PickupLocation).order_by(PickupLocation.name)).all()
        assert len(locations) >= 2
        locations[1].active = False
        inactive_location_id = locations[1].id
        expected_active_locations = len(locations) - 1
        now = datetime.now(UTC)
        for user in (user_a, user_b):
            session.add(
                Order(
                    user_id=user.id,
                    pickup_location_id=locations[0].id,
                    pickup_start_at=now + timedelta(days=1),
                    pickup_end_at=now + timedelta(days=1, hours=2),
                    pickup_location_name=locations[0].name,
                    pickup_location_address=locations[0].address_line,
                    total_nok=Decimal("129.00"),
                )
            )
        session.commit()

        context = AssistantToolContext(session=session, user=user_a)
        orders = _result_payload(registry.execute_json("get_user_orders", {}, context))
        pickups = _result_payload(registry.execute_json("get_pickup_locations", {}, context))

    assert orders["ok"] is True
    assert isinstance(orders["data"], list)
    assert len(orders["data"]) == 1
    assert pickups["ok"] is True
    assert isinstance(pickups["data"], list)
    assert len(pickups["data"]) == expected_active_locations
    assert str(inactive_location_id) not in {location["id"] for location in pickups["data"]}


def test_final_order_requires_prior_exact_user_confirmation(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        user = _user(session, "tool-user-a")
        meal_id = session.scalar(select(Meal.id).order_by(Meal.name))
        location_id = session.scalar(select(PickupLocation.id).order_by(PickupLocation.name))
        assert meal_id is not None
        assert location_id is not None
        registry.execute_json(
            "add_to_cart",
            {"meal_id": str(meal_id), "quantity": 2},
            AssistantToolContext(session=session, user=user),
        )

        prepared = _result_payload(
            registry.execute_json(
                "prepare_order",
                {"pickup_location_id": str(location_id)},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="prepare-request",
                    message="Prepare my order",
                ),
            )
        )
        assert prepared["ok"] is True
        prepared_data = prepared["data"]
        assert isinstance(prepared_data, dict)
        token = prepared_data["confirmation_token"]
        phrase = prepared_data["confirmation_phrase"]
        assert isinstance(token, str)
        assert isinstance(phrase, str)
        assert prepared_data["order_created"] is False
        assert session.scalar(select(func.count()).select_from(Order)) == 0

        same_turn = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": token},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="prepare-request",
                    message=phrase,
                ),
            )
        )
        assert same_turn["ok"] is False
        same_turn_error = same_turn["error"]
        assert isinstance(same_turn_error, dict)
        assert same_turn_error["code"] == "conflict"

        not_exact = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": token},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="confirm-request-1",
                    message=f"Please {phrase}",
                ),
            )
        )
        assert not_exact["ok"] is False
        not_exact_error = not_exact["error"]
        assert isinstance(not_exact_error, dict)
        assert not_exact_error["code"] == "conflict"

        confirmed = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": token},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="confirm-request-2",
                    message=phrase,
                ),
            )
        )
        assert confirmed["ok"] is True
        assert isinstance(confirmed["data"], dict)
        assert confirmed["data"]["total_nok"] == prepared_data["total_nok"]
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        confirmation = session.get(OrderConfirmation, UUID(token))
        assert confirmation is not None
        assert confirmation.consumed_at is not None

        cart = _result_payload(
            registry.execute_json(
                "get_cart",
                {},
                AssistantToolContext(session=session, user=user),
            )
        )
        cart_data = cart["data"]
        assert isinstance(cart_data, dict)
        assert cart_data["items"] == []


def test_order_confirmation_is_user_scoped_and_invalidated_by_cart_changes(
    engine: Engine,
) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        user_a = _user(session, "tool-user-a")
        user_b = _user(session, "tool-user-b")
        meals = list(session.scalars(select(Meal).order_by(Meal.name).limit(2)))
        location_id = session.scalar(select(PickupLocation.id).order_by(PickupLocation.name))
        assert len(meals) == 2
        assert location_id is not None
        registry.execute_json(
            "add_to_cart",
            {"meal_id": str(meals[0].id), "quantity": 1},
            AssistantToolContext(session=session, user=user_a),
        )
        prepared = _result_payload(
            registry.execute_json(
                "prepare_order",
                {"pickup_location_id": str(location_id)},
                AssistantToolContext(
                    session=session,
                    user=user_a,
                    request_id="prepare-a",
                    message="Prepare my order",
                ),
            )
        )
        data = prepared["data"]
        assert isinstance(data, dict)
        token = str(data["confirmation_token"])
        phrase = str(data["confirmation_phrase"])

        cross_user = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": token},
                AssistantToolContext(
                    session=session,
                    user=user_b,
                    request_id="confirm-b",
                    message=phrase,
                ),
            )
        )
        assert cross_user["ok"] is False
        cross_user_error = cross_user["error"]
        assert isinstance(cross_user_error, dict)
        assert cross_user_error["code"] == "not_found"

        registry.execute_json(
            "add_to_cart",
            {"meal_id": str(meals[1].id), "quantity": 1},
            AssistantToolContext(session=session, user=user_a),
        )
        changed_cart = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": token},
                AssistantToolContext(
                    session=session,
                    user=user_a,
                    request_id="confirm-a",
                    message=phrase,
                ),
            )
        )
        assert changed_cart["ok"] is False
        changed_cart_error = changed_cart["error"]
        assert isinstance(changed_cart_error, dict)
        assert changed_cart_error["code"] == "conflict"
        assert "Cart changed" in changed_cart_error["message"]
        assert session.scalar(select(func.count()).select_from(Order)) == 0


def test_order_tools_cannot_bypass_application_or_argument_validation(engine: Engine) -> None:
    registry = AssistantToolRegistry()
    with Session(engine) as session:
        user = _user(session, "tool-user-a")
        location_id = session.scalar(select(PickupLocation.id).order_by(PickupLocation.name))
        assert location_id is not None
        empty_cart = _result_payload(
            registry.execute_json(
                "prepare_order",
                {"pickup_location_id": str(location_id)},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="empty-cart",
                    message="Prepare my order",
                ),
            )
        )
        assert empty_cart["ok"] is False
        empty_cart_error = empty_cart["error"]
        assert isinstance(empty_cart_error, dict)
        assert empty_cart_error["code"] == "conflict"
        assert empty_cart_error["message"] == "Cart is empty"

        forged_token = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        model_supplied_confirmation = _result_payload(
            registry.execute_json(
                "create_order",
                {"confirmation_token": forged_token, "confirmed": True},
                AssistantToolContext(
                    session=session,
                    user=user,
                    request_id="forged",
                    message=f"CONFIRM ORDER {forged_token}",
                ),
            )
        )
        assert model_supplied_confirmation["ok"] is False
        validation_error = model_supplied_confirmation["error"]
        assert isinstance(validation_error, dict)
        assert validation_error["code"] == "invalid_tool_arguments"
        assert session.scalar(select(func.count()).select_from(Order)) == 0
