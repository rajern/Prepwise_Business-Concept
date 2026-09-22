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
* `database-migration-url` — privileged migration connection for the future T3.4 workflow

The Bicep deployment treats `database-url` as an existing secret without reading or recreating its
value. The Container App exposes it to the process as `DATABASE_URL` through a Key Vault secret
reference authenticated by `id-prepwise-prod-api`. The identity receives read access only to that
single secret. `database-migration-url` is not attached to the running application.

The backend additionally forces `sslmode=require` for production runtime connections. Local
development and CI keep using their existing local/containerised PostgreSQL configuration without
forced TLS or any Neon dependency.

Never commit a Neon host, username, password, connection string, generated `.env` file or secret
value. Rotating a Key Vault secret does not require a source-code change.
