# Neon production database boundary

Neon is the manually managed production PostgreSQL platform. It is not an Azure resource and is
not provisioned by Bicep. No Terraform or second infrastructure-as-code tool is introduced only
for Neon.

## Production setup

The production project and database use separate roles:

* dedicated SQL-created `prepwise_app_runtime`, with the explicit application grant map
  in `backend/src/prepwise_api/runtime_permissions.py`
* a migration/owner role reserved for Alembic schema migrations

Both connection strings must use the installed Psycopg 3 driver and TLS, for example:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

The actual values exist only in `kv-prepwise-prod-f5knfy`:

* `database-url` — pooled runtime connection for the Container App
* `database-migration-url` — privileged migration connection for deployment migrations
* `openai-api-key` — server-side AI provider credential (not a database connection)

The Bicep deployment treats `database-url` as an existing secret without reading or recreating its
value. The Container App exposes it to the process as `DATABASE_URL` through a Key Vault secret
reference authenticated by `id-prepwise-prod-api`. Separate secret-scoped role assignments give
the identity access to `database-url` and `openai-api-key`. `database-migration-url` is not attached
to the running application.

After new tables are migrated, the runtime PostgreSQL role must have the required DML privileges.
The AI limiter needs `SELECT`, `INSERT`, `UPDATE` and `DELETE` on `assistant_usage_events`, and
`SELECT`, `INSERT` and `UPDATE` on `assistant_quota_lock` (`FOR UPDATE` requires update privileges).
Deployment applies that reviewed grant map after Alembic, using the migration credential.
Do not grant wildcard privileges on future tables: update and test the explicit mapping when
introducing a table. CI checks that every ORM table has a grant plan. Runtime cannot migrate,
create schemas/roles/databases, truncate tables, grant rights or modify knowledge chunks.
Do not give it `neon_superuser` membership or schema-owner permissions. See the production review
and runtime-grant PostgreSQL tests for live evidence and isolated service verification.

The controlled 2026-09-30 switch version-pins the Container App Key Vault reference. Future
rotations must update that reference and deploy/restart before verification; do not assume a
latest-version secret is picked up immediately. Bicep currently uses the versionless secret URI:
an infrastructure reapply restores latest-version rotation behavior, not the pinned version.

Historical database-secret versions are disabled rather than deleted. The former privileged
database login is no longer used by the serving app, but disabling that login was denied to the
migration credential and needs a Neon administrator (TASKS N8). Runtime has no enabled access
to its historical credentials. Do not infer that the old account itself has been retired.
The manual `prepwise-set-user-role` operator command now needs an authorized migration/operator
connection: runtime intentionally cannot update customer roles through SQL.

The backend additionally forces `sslmode=require` for production runtime connections. Local
development and CI keep using their existing local/containerised PostgreSQL configuration without
forced TLS or any Neon dependency.

Never commit a Neon host, username, password, connection string, generated `.env` file or secret
value. Rotating a Key Vault secret does not require a source-code change.
