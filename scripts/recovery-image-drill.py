"""Offline image drill, allowed only against an explicitly named local test database."""

import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient
from prepwise_api.assistant import (
    AssistantReply,
    AssistantService,
    AssistantUnavailableError,
    get_assistant_service,
)
from prepwise_api.config import Settings, get_settings
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.seed import seed_database
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


class OfflineAssistant(AssistantService):
    def __init__(self) -> None:
        self.calls = 0

    async def respond_with_events(
        self, *, message, request_id, tool_context, on_event, stream_output=True
    ):
        self.calls += 1
        if message == "Synthetic partial write":
            await on_event({"type": "mutation", "mutation_status": "unknown"})
            # A real local mutation commits between the persistent pre-write and applied markers.
            from prepwise_api.models import Meal
            from prepwise_api.services.cart import add_user_cart_item
            from sqlalchemy import select

            meal = tool_context.session.scalar(select(Meal))
            add_user_cart_item(tool_context.session, tool_context.user.id, meal.id, 1)
            await on_event({"type": "mutation", "mutation_status": "applied"})
            raise AssistantUnavailableError("Synthetic failure after committed write")
        return AssistantReply(
            text="Offline recovery response", model="offline", response_id="offline"
        )


def drill() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if (
        os.environ.get("APP_ENV") != "test"
        or url.host not in {"127.0.0.1", "localhost", "host.docker.internal"}
        or url.database != "prepwise_ar_release_test"
        or os.environ.get("OPENAI_API_KEY")
    ):
        raise SystemExit(
            "Only the explicitly named local test database with no provider key is allowed"
        )
    settings = Settings()
    assert settings.assistant_streaming_enabled is False
    engine = create_engine(url, hide_parameters=True)
    seed_database(engine)
    assistant = OfflineAssistant()
    app.dependency_overrides[get_assistant_service] = lambda: assistant
    app.dependency_overrides[get_settings] = lambda: settings

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    headers = {"Authorization": "Bearer prepwise-e2e-customer"}
    try:
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200
            meal = client.get("/api/meals").json()[0]
            location = client.get("/api/pickup-locations").json()[0]
            day = client.get("/api/pickup-locations/options").json()["days"][0]["date"]
            selection = {
                "pickup_location_id": location["id"],
                "pickup_date": day,
                "pickup_slot": "16-18",
                "group_id": None,
            }
            group = client.post("/api/cart/groups", headers=headers, json={}).json()[
                "groups"
            ][-1]
            assert (
                client.post(
                    "/api/cart/items",
                    headers=headers,
                    json={
                        "meal_id": meal["id"],
                        "quantity": 1,
                        "group_id": group["id"],
                    },
                ).status_code
                == 201
            )
            assert (
                client.post(
                    "/api/cart/items",
                    headers=headers,
                    json={"meal_id": meal["id"], "quantity": 2},
                ).status_code
                == 201
            )
            review = client.post("/api/orders/review", headers=headers, json=selection)
            assert review.status_code == 200
            payload = {
                **selection,
                "review_fingerprint": review.json()["review_fingerprint"],
                "idempotency_key": str(uuid4()),
            }
            order = client.post("/api/orders", headers=headers, json=payload)
            assert order.status_code == 201
            order_id = order.json()["id"]
            cart = client.get("/api/cart", headers=headers).json()
            assert cart["total_quantity"] == 1
            assert (
                client.post(f"/api/orders/{order_id}/cancel", headers=headers).json()[
                    "status"
                ]
                == "cancelled"
            )
            assert (
                client.post(
                    "/api/cart/items",
                    headers=headers,
                    json={"meal_id": meal["id"], "quantity": 1},
                ).status_code
                == 201
            )
            replay = client.post("/api/orders", headers=headers, json=payload)
            assert replay.status_code == 201 and replay.json()["id"] == order_id
            assert replay.json()["status"] == "cancelled"
            assert (
                client.get("/api/cart", headers=headers).json()["total_quantity"] == 2
            )
            chat_headers = {**headers, "Accept": "text/event-stream"}
            chat = {"message": "Inspect cart", "idempotency_key": str(uuid4())}
            reply = client.post(
                "/api/assistant/messages", headers=chat_headers, json=chat
            )
            assert reply.status_code == 200
            assert reply.headers["content-type"].startswith("application/json")
            assert reply.json()["mutation_status"] == "none"
            duplicate = client.post(
                "/api/assistant/messages", headers=chat_headers, json=chat
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["code"] == "assistant_request_completed"
            partial = {
                "message": "Synthetic partial write",
                "idempotency_key": str(uuid4()),
            }
            failed = client.post(
                "/api/assistant/messages", headers=chat_headers, json=partial
            )
            assert (
                failed.status_code == 503
                and failed.json()["mutation_status"] == "applied"
            )
            blocked = client.post(
                "/api/assistant/messages", headers=chat_headers, json=partial
            )
            assert blocked.status_code == 409 and blocked.json()["retry_safe"] is False
            assert assistant.calls == 2
            assert (
                client.get("/api/cart", headers=headers).json()["total_quantity"] == 3
            )
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "a7b8c9d0e1f2"
            )
        print(
            json.dumps(
                {
                    "recovery_json": True,
                    "cancelled_keyed_order_replay": True,
                    "other_group_and_newer_cart_preserved": True,
                    "partial_write_replay_blocked": True,
                    "provider_calls": 0,
                }
            )
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


if __name__ == "__main__":
    drill()
