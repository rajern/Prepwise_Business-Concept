# Database migrations

Alembic manages the PostgreSQL schema. It reads the same `DATABASE_URL` as the FastAPI
application.

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
