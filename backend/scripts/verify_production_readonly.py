"""Inspect production metadata only; never print credentials or exception messages."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from prepwise_api.knowledge import load_knowledge_chunks


def main() -> int:
    az = shutil.which("az")
    if az is None:
        print('{"error_type":"AzureCliUnavailable"}')
        return 1
    try:
        result = subprocess.run(
            [
                az,
                "keyvault",
                "secret",
                "show",
                "--vault-name",
                "kv-prepwise-prod-f5knfy",
                "--name",
                "database-url",
                "--query",
                "value",
                "--output",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode or not result.stdout.strip():
            print('{"error_type":"RuntimeCredentialReadDenied"}')
            return 1
        engine = create_engine(
            result.stdout.strip(),
            echo=False,
            connect_args={"sslmode": "require", "connect_timeout": 15},
            hide_parameters=True,
        )
        runtime_username = make_url(result.stdout.strip()).username
        del result
        migration = subprocess.run(
            [
                az,
                "keyvault",
                "secret",
                "show",
                "--vault-name",
                "kv-prepwise-prod-f5knfy",
                "--name",
                "database-migration-url",
                "--query",
                "value",
                "--output",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        same_identity = None
        if migration.returncode == 0 and migration.stdout.strip():
            same_identity = runtime_username == make_url(migration.stdout.strip()).username
        del migration
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '15s'"))
            report: dict[str, Any] = {
                "transaction_read_only": connection.scalar(text("SHOW transaction_read_only"))
            }
            report["role"] = dict(
                connection.execute(
                    text(
                        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                )
                .mappings()
                .one()
            )
            report["same_login_as_migration"] = same_identity
            report["role_memberships"] = list(
                connection.scalars(
                    text(
                        "SELECT r.rolname FROM pg_auth_members m "
                        "JOIN pg_roles r ON r.oid = m.roleid "
                        "WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
                    )
                )
            )
            report["membership_count"] = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_auth_members "
                    "WHERE member = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
                )
            )
            report["tls"] = dict(
                connection.execute(
                    text("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
                )
                .mappings()
                .one()
            )
            report["client_tls_in_use"] = bool(
                cast(
                    psycopg.Connection[tuple[Any, ...]], connection.connection.driver_connection
                ).pgconn.ssl_in_use
            )
            report["schema_create"] = connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            )
            report["quota_privileges"] = []
            for table in ("assistant_usage_events", "assistant_quota_lock"):
                item: dict[str, Any] = {"table": table}
                for privilege in (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "TRUNCATE",
                    "REFERENCES",
                    "TRIGGER",
                ):
                    item[privilege] = connection.scalar(
                        text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                        {"table": f"public.{table}", "privilege": privilege},
                    )
                    item[f"{privilege}_GRANT"] = connection.scalar(
                        text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                        {"table": f"public.{table}", "privilege": f"{privilege} WITH GRANT OPTION"},
                    )
                item["owned_by_runtime"] = connection.scalar(
                    text(
                        "SELECT c.relowner = r.oid FROM pg_class c JOIN pg_roles r "
                        "ON r.rolname = current_user WHERE c.oid = to_regclass(:table)"
                    ),
                    {"table": f"public.{table}"},
                )
                report["quota_privileges"].append(item)
            report["alembic_versions"] = list(
                connection.scalars(text("SELECT version_num FROM alembic_version"))
            )
            report["meal_count"] = connection.scalar(text("SELECT count(*) FROM meals"))
            actual = connection.execute(
                text(
                    "SELECT source_path, chunk_index, content_hash, embedding_model "
                    "FROM knowledge_chunks"
                )
            ).all()
            drafts = load_knowledge_chunks(
                Path(__file__).resolve().parents[2] / "docs" / "knowledge-base"
            )
            expected = {
                (d.source_path, d.chunk_index, d.content_hash, "text-embedding-3-small")
                for d in drafts
            }
            report["knowledge"] = {
                "actual_chunks": len(actual),
                "expected_chunks": len(expected),
                "matches_local_documents_and_model": set(actual) == expected,
            }
            connection.rollback()
        engine.dispose()
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as error:
        # SDK/SQL exceptions can contain URLs, parameters or raw credential output.
        print(json.dumps({"error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
