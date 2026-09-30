"""Disable the former privileged login only after the verified replacement release."""

import argparse
import json
import re
import urllib.request
from typing import Any

from provision_runtime_role import APP, RESOURCE_GROUP, VAULT, az_json, engine_for, validate_runtime
from sqlalchemy import text
from sqlalchemy.engine import make_url

from prepwise_api.runtime_permissions import RUNTIME_ROLE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-approved", action="store_true")
    parser.add_argument("--previous-version", required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    if not args.apply_approved or not re.fullmatch(r"[a-f0-9]{32}", args.previous_version):
        parser.error("Explicit approval and exact previous version required")
    if not re.fullmatch(r"[a-f0-9]{40}", args.expected_sha):
        parser.error("Exact expected release SHA required")
    try:
        app: dict[str, Any] = az_json(
            "containerapp", "show", "--resource-group", RESOURCE_GROUP, "--name", APP
        )
        desired = app["properties"]["template"]["containers"][0]["image"]
        if desired != f"ghcr.io/rajern/prepwise-api:{args.expected_sha}":
            raise RuntimeError("Unexpected serving release")
        if app["properties"]["latestRevisionName"] != app["properties"]["latestReadyRevisionName"]:
            raise RuntimeError("Latest revision is not ready")
        origin = "https://" + app["properties"]["configuration"]["ingress"]["fqdn"]
        for path in ("/health/live", "/health/ready", "/api/meals"):
            with urllib.request.urlopen(origin + path, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError("Public smoke failed")
        current = az_json(
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            "kv-prepwise-prod-f5knfy",
            "--name",
            "database-url",
        )
        old = az_json(
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            "kv-prepwise-prod-f5knfy",
            "--name",
            "database-url",
            "--version",
            args.previous_version,
        )
        migration = az_json(
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            "kv-prepwise-prod-f5knfy",
            "--name",
            "database-migration-url",
        )
        old_login = make_url(old["value"]).username
        if not old_login or old_login in {RUNTIME_ROLE, make_url(migration["value"]).username}:
            raise RuntimeError("Cannot retire current runtime or migration login")
        if make_url(current["value"]).username != RUNTIME_ROLE:
            raise RuntimeError("Current secret is not the replacement runtime")
        runtime = engine_for(current["value"])
        validate_runtime(runtime)
        runtime.dispose()
        owner = engine_for(migration["value"])
        with owner.begin() as connection:
            # Runtime probe above is disposed; remaining sessions follow public app traffic.
            live = connection.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE usename = :role"),
                {"role": RUNTIME_ROLE},
            )
            if not live:
                raise RuntimeError("No replacement application database session observed")
            quoted = connection.dialect.identifier_preparer.quote_identifier(old_login)
            connection.exec_driver_sql(f"ALTER ROLE {quoted} NOLOGIN")
        with owner.begin() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE usename = :role AND pid <> pg_backend_pid()"
                ),
                {"role": old_login},
            )
        with owner.connect() as connection:
            remaining = connection.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE usename = :role"),
                {"role": old_login},
            )
            login = connection.scalar(
                text("SELECT rolcanlogin FROM pg_roles WHERE rolname=:role"), {"role": old_login}
            )
        owner.dispose()
        if login or remaining:
            raise RuntimeError("Former login still active; operator review required")
        print(
            json.dumps(
                {
                    "former_runtime_login_disabled": True,
                    "former_runtime_sessions": remaining,
                    "replacement_application_sessions_observed": live,
                    "business_rows_changed": False,
                    "previous_secret_uri": f"{VAULT}/secrets/database-url/{args.previous_version}",
                }
            )
        )
        return 0
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
