from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prepwise_api.models import Base, User, UserRole
from prepwise_api.user_roles import set_user_role


def test_set_user_role_explicitly_updates_existing_user() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session, session.begin():
        user = User(
            external_subject="tenant-id:object-id",
            email="admin@example.com",
            display_name="Admin User",
        )
        session.add(user)
        session.flush()
        user_id = user.id

    change = set_user_role(engine, "admin@example.com", UserRole.ADMIN)

    assert change.user_id == user_id
    assert change.previous_role is UserRole.CUSTOMER
    assert change.new_role is UserRole.ADMIN

    with Session(engine) as session:
        updated_user = session.scalar(select(User))
        assert updated_user is not None
        assert updated_user.role is UserRole.ADMIN

    engine.dispose()
