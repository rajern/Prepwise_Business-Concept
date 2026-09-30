# Neon production database boundary

Neon is the manually managed production PostgreSQL platform. It is not an Azure resource and is
not provisioned by Bicep. No Terraform or second infrastructure-as-code tool is introduced only
for Neon.

## Production setup

The production project and database already exist with separate roles:

* a least-privileged runtime role used by the FastAPI application
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
Confirm owner default privileges or grant equivalent runtime rights before release;
the repository does not verify the live Neon grants. Do not give runtime schema-owner permissions.

The backend additionally forces `sslmode=require` for production runtime connections. Local
development and CI keep using their existing local/containerised PostgreSQL configuration without
forced TLS or any Neon dependency.

Never commit a Neon host, username, password, connection string, generated `.env` file or secret
value. Rotating a Key Vault secret does not require a source-code change.
