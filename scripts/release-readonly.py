"""Read-only release metadata checks. Never print credentials or customer records."""

import argparse
import json
import subprocess
from pathlib import Path

from prepwise_api.knowledge import load_knowledge_chunks
from prepwise_api.runtime_permissions import RUNTIME_ROLE, RUNTIME_TABLE_PRIVILEGES
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def inspect(head: str, require_index_match: bool) -> dict[str, object]:
    result = subprocess.run(
        [
            "az.cmd",
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
            "--only-show-errors",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    url = make_url(result.stdout.strip())
    if not (
        url.host and url.host.endswith(".neon.tech") and url.username == RUNTIME_ROLE
    ):
        raise ValueError("Unexpected runtime identity/host")
    engine = create_engine(
        url, hide_parameters=True, connect_args={"connect_timeout": 20}
    )
    try:
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '20000ms'")
            role = connection.scalar(text("SELECT current_user"))
            assert role == RUNTIME_ROLE, "runtime_identity"
            assert connection.scalar(text("SHOW transaction_read_only")) == "on", (
                "read_only"
            )
            # Neon may pool the server connection; validate this client's TLS instead.
            assert connection.connection.driver_connection.pgconn.ssl_in_use, (
                "client_tls"
            )
            actual_head = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            assert actual_head == head, f"schema_head={actual_head}"
            assert not any(
                connection.execute(
                    text(
                        "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                        "FROM pg_roles WHERE rolname=current_user"
                    )
                ).one()
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_auth_members WHERE member="
                        "(SELECT oid FROM pg_roles WHERE rolname=current_user)"
                    )
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT has_schema_privilege(current_user,'public','CREATE')")
                )
                is False
            )
            tables = set(
                connection.scalars(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            )
            expected = dict(RUNTIME_TABLE_PRIVILEGES)
            if head == "f6a7b8c9d0e1":
                expected.pop("assistant_requests")
            assert tables == set(expected), "public_table_set"
            for table, privileges in expected.items():
                actual = {
                    privilege
                    for privilege in (
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "TRUNCATE",
                        "REFERENCES",
                        "TRIGGER",
                    )
                    if connection.scalar(
                        text(
                            "SELECT has_table_privilege(current_user,:table,:privilege)"
                        ),
                        {"table": f"public.{table}", "privilege": privilege},
                    )
                }
                assert actual == set(privileges), f"runtime_privileges:{table}"
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE grantee=current_user AND table_schema='public' AND is_grantable='YES'"
                    )
                )
                == 0
            )
            chunks = connection.execute(
                text(
                    "SELECT source_path,chunk_index,content_hash,embedding_model FROM knowledge_chunks"
                )
            ).all()
            stored = {(row[0], row[1]): (row[2], row[3]) for row in chunks}
            drafts = load_knowledge_chunks(
                Path(__file__).resolve().parents[1] / "docs/knowledge-base"
            )
            proposed = {
                (draft.source_path, draft.chunk_index): (
                    draft.content_hash,
                    "text-embedding-3-small",
                )
                for draft in drafts
            }
            unchanged = sum(stored.get(key) == value for key, value in proposed.items())
            if require_index_match:
                assert stored == proposed
            meals = connection.scalar(text("SELECT count(*) FROM meals"))
            assert isinstance(meals, int) and meals > 0
            legacy_login = connection.scalar(
                text("SELECT rolcanlogin FROM pg_roles WHERE rolname='prepwise_app'")
            )
            return {
                "schema": actual_head,
                "runtime_tables": len(expected),
                "runtime_grants_exact": True,
                "restricted_runtime_tls": True,
                "meals": meals,
                "stored_chunks": len(stored),
                "proposed_chunks": len(proposed),
                "unchanged_chunks": unchanged,
                "changed_or_new_chunks": len(proposed) - unchanged,
                "stale_chunks": len(set(stored) - set(proposed)),
                "index_matches": stored == proposed,
                "legacy_role_allows_login": legacy_login,
                "production_writes": False,
                "model_calls": 0,
            }
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-head", required=True, choices=["f6a7b8c9d0e1", "a7b8c9d0e1f2"]
    )
    parser.add_argument("--require-index-match", action="store_true")
    arguments = parser.parse_args()
    try:
        print(
            json.dumps(
                inspect(arguments.expect_head, arguments.require_index_match), indent=2
            )
        )
    except AssertionError as error:
        print(f"Read-only release inspection failed: metadata assertion ({error})")
        raise SystemExit(1) from None
    except Exception as error:  # noqa: BLE001 -- credentials must never enter error output
        print(f"Read-only release inspection failed: {type(error).__name__}")
        raise SystemExit(1) from None
