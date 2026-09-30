"""Exercise least-privileged runtime grants only in a disposable local PostgreSQL DB.

The NOLOGIN role, private schema and all test data live in one rolled-back owner
transaction. Service commits release savepoints rather than persisting test data.
No production credentials or embedding/model API calls are used.
"""

import asyncio
import os
from collections.abc import Iterator, Sequence
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from prepwise_api.api.admin_meals import create_admin_meal, update_admin_meal
from prepwise_api.api.admin_orders import update_admin_order_status
from prepwise_api.api.admin_pickup_locations import (
    create_admin_pickup_location,
    update_admin_pickup_location,
)
from prepwise_api.auth import AccessTokenClaims, get_current_user, require_admin
from prepwise_api.config import Settings
from prepwise_api.knowledge import KnowledgeRetriever
from prepwise_api.models import Allergen, AssistantUsageEvent, Base, KnowledgeChunk, User, UserRole
from prepwise_api.models.enums import OrderStatus
from prepwise_api.models.knowledge import KNOWLEDGE_EMBEDDING_DIMENSIONS
from prepwise_api.runtime_permissions import RUNTIME_TABLE_PRIVILEGES, apply_runtime_grants
from prepwise_api.schemas import MealAdminWrite, OrderStatusUpdate, PickupLocationAdminWrite
from prepwise_api.services.assistant_quota import (
    release_assistant_request,
    reserve_assistant_request,
)
from prepwise_api.services.cart import (
    add_user_cart_item,
    get_user_cart,
    remove_user_cart_item,
    set_user_cart_item_quantity,
)
from prepwise_api.services.orders import (
    confirm_user_order,
    create_user_order,
    prepare_user_order_confirmation,
)
from prepwise_api.services.pickup_schedule import list_pickup_options


class _LocalEmbeddingProvider:
    model = "runtime-grant-test"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (KNOWLEDGE_EMBEDDING_DIMENSIONS - 1) for _ in texts]


def test_every_application_table_has_a_reviewed_grant_plan() -> None:
    assert set(Base.metadata.tables) == set(RUNTIME_TABLE_PRIVILEGES) - {"alembic_version"}


@pytest.fixture
def runtime_session() -> Iterator[tuple[Session, str, str]]:
    value = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL for local PostgreSQL runtime-grant tests")
    url = make_url(value)
    assert url.drivername.startswith("postgresql")
    assert url.host in {"127.0.0.1", "localhost"}
    assert url.database is not None and (
        url.database.endswith("_ci")
        or url.database.endswith("_test")
        or url.database == "prepwise_round1"
    ), "Runtime-grant tests require an explicitly disposable local database"
    suffix = uuid4().hex
    schema = f"runtime_grant_test_{suffix}"
    role = f"runtime_grant_role_{suffix}"
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as owner_connection:
            transaction = owner_connection.begin()
            try:
                owner_connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
                owner_connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                owner_connection.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC'))
                connection = owner_connection.execution_options(schema_translate_map={None: schema})
                Base.metadata.create_all(connection)
                connection.execute(text(f'CREATE TABLE "{schema}".future_table (id integer)'))
                connection.execute(
                    text(f'CREATE TABLE "{schema}".alembic_version (version_num varchar(32))')
                )
                with Session(connection, join_transaction_mode="create_savepoint") as owner:
                    owner.add(Allergen(code="milk", name="Melk", name_en="Milk"))
                    owner.add(User(external_subject="grant-admin", role=UserRole.ADMIN))
                    owner.add(
                        KnowledgeChunk(
                            source_path="local-test.md",
                            source_title="Local test",
                            chunk_index=0,
                            content="Pickup is tomorrow at the chosen location and time.",
                            content_hash="0" * 64,
                            embedding_model=_LocalEmbeddingProvider.model,
                            embedding=[1.0] + [0.0] * (KNOWLEDGE_EMBEDDING_DIMENSIONS - 1),
                        )
                    )
                    owner.commit()
                apply_runtime_grants(connection, role, schema=schema)
                connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                with Session(connection, join_transaction_mode="create_savepoint") as session:
                    yield session, schema, role
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _meal_payload(**changes: object) -> MealAdminWrite:
    values: dict[str, object] = {
        "name": "Lokalt testmåltid",
        "name_en": "Local test meal",
        "description": "Kun testdata.",
        "description_en": "Test data only.",
        "price_nok": Decimal("25.00"),
        "calories": 200,
        "protein_grams": Decimal("20.00"),
        "carbohydrate_grams": Decimal("15.00"),
        "fat_grams": Decimal("5.00"),
        "ingredients": ["Testmelk", "Testgrønnsak"],
        "ingredients_en": ["Test milk", "Test vegetable"],
        "allergen_codes": ["milk"],
    }
    values.update(changes)
    return MealAdminWrite.model_validate(values)


def test_runtime_grants_support_real_application_flows(
    runtime_session: tuple[Session, str, str],
) -> None:
    session, _, _ = runtime_session
    claims = AccessTokenClaims("local", "grant-customer", "customer", None, "Local test")
    user = get_current_user(claims, session)
    assert get_current_user(claims, session).id == user.id
    admin = session.scalar(select(User).where(User.external_subject == "grant-admin"))
    assert admin is not None
    assert require_admin(admin).id == admin.id

    meal = create_admin_meal(_meal_payload(), admin, session)
    meal = update_admin_meal(
        meal.id,
        _meal_payload(ingredients=["Testmelk"], ingredients_en=["Updated test milk"]),
        admin,
        session,
    )
    assert meal.ingredients == ["Testmelk"]
    assert meal.allergens[0].code == "milk"
    location = create_admin_pickup_location(
        PickupLocationAdminWrite(
            name="Local test pickup", address_line="Test address", postal_code="0000", city="Oslo"
        ),
        admin,
        session,
    )
    location = update_admin_pickup_location(
        location.id,
        PickupLocationAdminWrite(
            name="Local test pickup",
            address_line="Updated address",
            postal_code="0000",
            city="Oslo",
        ),
        admin,
        session,
    )
    assert location.address_line == "Updated address"

    cart = add_user_cart_item(session, user.id, meal.id, 1)
    cart = set_user_cart_item_quantity(session, user.id, cart.items[0].id, 2)
    assert cart.total_quantity == 2
    assert remove_user_cart_item(session, user.id, cart.items[0].id).total_quantity == 0
    add_user_cart_item(session, user.id, meal.id, 1)
    day = list_pickup_options().days[0]
    prepared = prepare_user_order_confirmation(
        session,
        user.id,
        location.id,
        "grant-prepare",
        pickup_date=day.date,
        pickup_slot="16-18",
    )
    order = confirm_user_order(
        session,
        user.id,
        UUID(str(prepared["confirmation_token"])),
        "grant-confirm",
        str(prepared["confirmation_phrase"]),
    )
    assert get_user_cart(session, user.id).total_quantity == 0
    updated = update_admin_order_status(
        order.id, OrderStatusUpdate(status=OrderStatus.PREPARING), admin, session
    )
    assert updated.status == OrderStatus.PREPARING
    add_user_cart_item(session, user.id, meal.id, 1)
    checkout = create_user_order(
        session, user.id, location.id, pickup_date=day.date, pickup_slot="18-20"
    )
    assert checkout.items[0].meal_id == meal.id

    event_id = reserve_assistant_request(session, user.id, Settings(app_env="production"))
    release_assistant_request(session, event_id)
    event = session.get(AssistantUsageEvent, event_id)
    assert event is not None and event.released_at is not None
    matches = asyncio.run(
        KnowledgeRetriever(_LocalEmbeddingProvider()).retrieve(session, "When is pickup?")
    )
    assert len(matches) == 1 and matches[0].source_path == "local-test.md"


def test_runtime_grants_deny_escalation_and_out_of_scope_writes(
    runtime_session: tuple[Session, str, str],
) -> None:
    session, schema, role = runtime_session
    attributes = session.execute(
        text(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = :role"
        ),
        {"role": role},
    ).one()
    assert not any(attributes)
    assert (
        session.scalar(
            text("SELECT has_schema_privilege(current_user, :schema, 'CREATE')"), {"schema": schema}
        )
        is False
    )
    assert (
        session.scalar(
            text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")
        )
        is False
    )
    assert (
        session.scalar(
            text("SELECT has_table_privilege(current_user, :table, 'SELECT WITH GRANT OPTION')"),
            {"table": f"{schema}.meals"},
        )
        is False
    )
    assert (
        session.scalar(
            text("SELECT count(*) FROM pg_auth_members WHERE member = current_user::regrole")
        )
        == 0
    )

    forbidden = [
        f'CREATE TABLE "{schema}".unauthorized (id integer)',
        f'ALTER TABLE "{schema}".meals ADD COLUMN unauthorized integer',
        f'TRUNCATE "{schema}".assistant_usage_events',
        f'DELETE FROM "{schema}".users',
        f"UPDATE \"{schema}\".users SET role = 'admin'",
        f'DELETE FROM "{schema}".orders',
        f'DELETE FROM "{schema}".order_items',
        f"UPDATE \"{schema}\".order_items SET meal_name = 'tampered'",
        f'DELETE FROM "{schema}".order_confirmations',
        f'DELETE FROM "{schema}".assistant_quota_lock',
        f"UPDATE \"{schema}\".knowledge_chunks SET content = 'tampered'",
        f'DELETE FROM "{schema}".knowledge_chunks',
        f'INSERT INTO "{schema}".knowledge_chunks DEFAULT VALUES',
        f'SELECT * FROM "{schema}".alembic_version',
        f'SELECT * FROM "{schema}".future_table',
        f'INSERT INTO "{schema}".future_table VALUES (1)',
    ]
    for statement in forbidden:
        with pytest.raises(ProgrammingError) as failure, session.begin_nested():
            session.execute(text(statement))
        assert getattr(failure.value.orig, "sqlstate", None) == "42501"
