# Database migrations

Alembic manages the PostgreSQL schema and reads `DATABASE_URL`. Local development uses the same
development URL as the application. A production migration process must instead populate
`DATABASE_URL` from the Key Vault secret `database-migration-url`, which uses the dedicated
migration/owner role and requires TLS. That credential must never be injected into the running
Container App.

Create a migration after changing the SQLAlchemy models:

```powershell
.venv\Scripts\python -m alembic revision --autogenerate -m "describe change"
```

Apply or revert migrations:

```powershell
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic downgrade -1
```

Seed data must not be added to schema migrations.

Seed the development catalogue separately after applying migrations:

```powershell
.venv\Scripts\python -m prepwise_api.seed
```

The production deployment runs `prepwise-seed-if-empty` after migrations. It creates the initial
portfolio demo catalogue only when no meals exist, so later administrative changes are not reset
by subsequent deployments.
