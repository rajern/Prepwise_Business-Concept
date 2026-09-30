"""Owner-approved, one-time runtime credential switch; no secrets in files or output."""

import argparse
import json
import secrets
import shutil
import subprocess
import urllib.request
from typing import Any, cast

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from prepwise_api.runtime_permissions import (
    RUNTIME_ROLE,
    RUNTIME_TABLE_PRIVILEGES,
    apply_runtime_grants,
)

VAULT = "https://kv-prepwise-prod-f5knfy.vault.azure.net"
RESOURCE_GROUP = "rg-prepwise-prod"
APP = "ca-prepwise-prod"


def az_json(*args: str) -> Any:
    executable = shutil.which("az")
    if executable is None:
        raise RuntimeError("Azure CLI unavailable")
    result = subprocess.run(
        [executable, *args, "--output", "json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Azure command denied or failed")
    return json.loads(result.stdout)


def engine_for(value: str) -> Engine:
    return create_engine(
        value,
        echo=False,
        hide_parameters=True,
        connect_args={"sslmode": "require", "connect_timeout": 15},
    )


def validate_runtime(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        flags = connection.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        if any(flags):
            raise RuntimeError("Runtime attributes remain privileged")
        if connection.scalar(
            text(
                "SELECT count(*) FROM pg_auth_members WHERE member="
                "(SELECT oid FROM pg_roles WHERE rolname=current_user)"
            )
        ):
            raise RuntimeError("Unexpected inherited role")
        if connection.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')")):
            raise RuntimeError("Runtime has schema CREATE")
        for table, allowed in RUNTIME_TABLE_PRIVILEGES.items():
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            ):
                granted = connection.scalar(
                    text("SELECT has_table_privilege(current_user,:table,:privilege)"),
                    {"table": f"public.{table}", "privilege": privilege},
                )
                if granted != (privilege in allowed):
                    raise RuntimeError("Unexpected effective table grant")
                grant_option = connection.scalar(
                    text("SELECT has_table_privilege(current_user,:table,:privilege)"),
                    {"table": f"public.{table}", "privilege": privilege + " WITH GRANT OPTION"},
                )
                if grant_option:
                    raise RuntimeError("Runtime has grant option")
            connection.exec_driver_sql(f'SELECT 1 FROM public."{table}" LIMIT 0')
        if not cast(
            psycopg.Connection[tuple[Any, ...]], connection.connection.driver_connection
        ).pgconn.ssl_in_use:
            raise RuntimeError("Client TLS not in use")
        connection.rollback()


def put_secret(value: str) -> str:
    token = az_json("account", "get-access-token", "--resource", "https://vault.azure.net")[
        "accessToken"
    ]
    request = urllib.request.Request(
        f"{VAULT}/secrets/database-url?api-version=7.4",
        data=json.dumps({"value": value}).encode(),
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return str(json.loads(response.read())["id"])


def bind_secret(uri: str, identity: str) -> None:
    az_json(
        "containerapp",
        "secret",
        "set",
        "--resource-group",
        RESOURCE_GROUP,
        "--name",
        APP,
        "--secrets",
        f"database-url=keyvaultref:{uri},identityref:{identity}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-approved", action="store_true")
    args = parser.parse_args()
    if not args.apply_approved:
        parser.error("Explicit owner approval required")
    phase = "preflight"
    old: dict[str, Any] | None = None
    binding: dict[str, Any] | None = None
    switched = False
    try:
        old = az_json(
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            "kv-prepwise-prod-f5knfy",
            "--name",
            "database-url",
        )
        owner = az_json(
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            "kv-prepwise-prod-f5knfy",
            "--name",
            "database-migration-url",
        )
        binding = az_json(
            "containerapp",
            "show",
            "--resource-group",
            RESOURCE_GROUP,
            "--name",
            APP,
            "--query",
            "properties.configuration.secrets[?name=='database-url'] | [0]",
        )
        if not binding or not binding.get("keyVaultUrl") or not binding.get("identity"):
            raise RuntimeError("Expected Key Vault managed-identity binding missing")
        if make_url(old["value"]).username == RUNTIME_ROLE:
            raise RuntimeError("Already switched; use read-only verification, not a rerun")
        password = secrets.token_urlsafe(48)
        new_url = make_url(old["value"]).set(username=RUNTIME_ROLE, password=password)
        owner_engine = engine_for(owner["value"])
        phase = "create_role_and_grants"
        with owner_engine.begin() as connection:
            if connection.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": RUNTIME_ROLE}
            ):
                raise RuntimeError("Role already exists; operator recovery review required")
            driver = cast(
                psycopg.Connection[tuple[Any, ...]], connection.connection.driver_connection
            )
            # Neon requires a plaintext password in this protocol (not pre-hashed).
            # Keep it in memory and require TLS; no SQL echo or exception text is emitted.
            if not driver.pgconn.ssl_in_use:
                raise RuntimeError("Owner client TLS not in use")
            with driver.cursor() as cursor:
                phase = "create_restricted_login"
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}"
                    ).format(sql.Identifier(RUNTIME_ROLE), sql.Literal(password))
                )
            database = connection.scalar(text("SELECT current_database()"))
            phase = "grant_database_connect"
            quoted_database = connection.dialect.identifier_preparer.quote_identifier(str(database))
            connection.exec_driver_sql(
                f'GRANT CONNECT ON DATABASE {quoted_database} TO "{RUNTIME_ROLE}"'
            )
            phase = "grant_reviewed_tables"
            apply_runtime_grants(connection)
            phase = "commit_role_and_grants"
        owner_engine.dispose()
        phase = "validate_new_login"
        runtime_engine = engine_for(new_url.render_as_string(hide_password=False))
        validate_runtime(runtime_engine)
        runtime_engine.dispose()
        phase = "key_vault_switch"
        new_uri = put_secret(new_url.render_as_string(hide_password=False))
        switched = True
        phase = "container_secret_binding"
        # Version-pin for immediate deterministic use; prior KV version remains intact.
        bind_secret(new_uri, binding["identity"])
        print(
            json.dumps(
                {
                    "status": "switched_and_prevalidated",
                    "runtime_role": RUNTIME_ROLE,
                    "recovery_secret_uri": old["id"],
                    "new_secret_uri": new_uri,
                    "business_rows_changed": False,
                    "next_step": "deploy verified code; check serving runtime identity",
                }
            )
        )
        return 0
    except Exception as error:
        report: dict[str, Any] = {"error_type": type(error).__name__, "phase": phase}
        original = getattr(error, "orig", error)
        report["sqlstate"] = getattr(original, "sqlstate", None)
        # Classify diagnostics using a fixed vocabulary, never render server text.
        diagnostic = getattr(original, "diag", None)
        primary = (getattr(diagnostic, "message_primary", "") or "").lower()
        report["diagnostic_categories"] = [
            category
            for category in (
                "permission",
                "password",
                "role",
                "scram",
                "transaction",
                "pool",
                "neon",
                "unsupported",
                "parameter",
                "create",
                "empty",
                "null",
                "iteration",
                "control plane",
                "invalid",
            )
            if category in primary
        ]
        if switched and old is not None and binding is not None:
            try:
                restored_uri = put_secret(old["value"])
                bind_secret(restored_uri, binding["identity"])
                report["credential_switch_recovered"] = True
            except Exception as recovery_error:
                report["recovery_error_type"] = type(recovery_error).__name__
        print(json.dumps(report))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
