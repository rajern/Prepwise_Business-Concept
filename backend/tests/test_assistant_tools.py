import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.assistant_tools import AssistantToolContext, AssistantToolRegistry
from prepwise_api.models import Base, Meal, Order, PickupLocation, User
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
