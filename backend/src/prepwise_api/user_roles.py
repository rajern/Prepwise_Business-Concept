import argparse
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from prepwise_api.database import get_engine
from prepwise_api.models import User, UserRole


class UserNotFoundError(Exception):
    """No local user has the supplied email address."""


@dataclass(frozen=True, slots=True)
class RoleChange:
    user_id: UUID
    email: str
    previous_role: UserRole
    new_role: UserRole


def set_user_role(engine: Engine, email: str, role: UserRole) -> RoleChange:
    """Explicitly assign a local application role to one existing user."""
    with Session(engine) as session, session.begin():
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            raise UserNotFoundError(email)

        change = RoleChange(
            user_id=user.id,
            email=email,
            previous_role=user.role,
            new_role=role,
        )
        user.role = role

    return change


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign a Prepwise local-user role.")
    parser.add_argument("--email", required=True, help="Exact email of an existing local user.")
    parser.add_argument(
        "--role",
        required=True,
        choices=tuple(role.value for role in UserRole),
        help="Role to assign.",
    )
    arguments = parser.parse_args()

    try:
        change = set_user_role(
            get_engine(),
            email=arguments.email,
            role=UserRole(arguments.role),
        )
    except UserNotFoundError as error:
        raise SystemExit(f"No local user found for {error.args[0]}") from error

    print(
        f"Updated {change.email} ({change.user_id}): "
        f"{change.previous_role.value} -> {change.new_role.value}"
    )


if __name__ == "__main__":
    main()
