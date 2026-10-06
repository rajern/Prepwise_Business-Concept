"""Explicit application grants, applied by the migration owner after schema upgrades."""

import argparse

from sqlalchemy import text
from sqlalchemy.engine import Connection

from prepwise_api.database import get_engine

RUNTIME_ROLE = "prepwise_app_runtime"
RUNTIME_TABLE_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "users": ("SELECT", "INSERT"),
    "meals": ("SELECT", "INSERT", "UPDATE"),
    "ingredients": ("SELECT", "INSERT", "UPDATE"),
    "allergens": ("SELECT",),
    "meal_ingredients": ("SELECT", "INSERT", "DELETE"),
    "meal_allergens": ("SELECT", "INSERT", "DELETE"),
    "pickup_locations": ("SELECT", "INSERT", "UPDATE"),
    "cart_items": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "cart_groups": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "orders": ("SELECT", "INSERT", "UPDATE"),
    "order_items": ("SELECT", "INSERT"),
    "order_confirmations": ("SELECT", "INSERT", "UPDATE"),
    "assistant_usage_events": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "assistant_quota_lock": ("SELECT", "INSERT", "UPDATE"),
    "assistant_requests": ("SELECT", "INSERT", "UPDATE"),
    "knowledge_chunks": ("SELECT",),
    "alembic_version": ("SELECT",),
}


def apply_runtime_grants(
    connection: Connection, role: str = RUNTIME_ROLE, *, schema: str = "public"
) -> None:
    """Grant reviewed capabilities only; never create roles or touch business rows."""
    if connection.dialect.name != "postgresql":
        raise ValueError("Runtime permissions require PostgreSQL")
    flags = connection.execute(
        text(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = :role"
        ),
        {"role": role},
    ).one_or_none()
    if flags is None or any(flags):
        raise ValueError("Missing or overprivileged runtime role")
    memberships = connection.scalar(
        text(
            "SELECT count(*) FROM pg_auth_members WHERE member = "
            "(SELECT oid FROM pg_roles WHERE rolname = :role)"
        ),
        {"role": role},
    )
    if memberships:
        raise ValueError("Runtime role must not inherit other roles")
    quote = connection.dialect.identifier_preparer.quote_identifier
    role_sql, schema_sql = quote(role), quote(schema)
    connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema_sql} TO {role_sql}")
    # Only this dedicated role's table grants change, in the caller's transaction.
    for table, privileges in RUNTIME_TABLE_PRIVILEGES.items():
        if table == "alembic_version" and schema != "public":
            continue
        table_sql = f"{schema_sql}.{quote(table)}"
        connection.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON TABLE {table_sql} FROM {role_sql}")
        permission_sql = ", ".join(privileges)
        connection.exec_driver_sql(f"GRANT {permission_sql} ON TABLE {table_sql} TO {role_sql}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        with get_engine().begin() as connection:
            apply_runtime_grants(connection)
        print("Reviewed runtime grants applied")
    except Exception as error:
        print(f"Runtime grant application failed: {type(error).__name__}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
