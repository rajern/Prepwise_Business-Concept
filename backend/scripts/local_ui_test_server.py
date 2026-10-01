"""Disposable SQLite API for local browser UX checks, NOT PostgreSQL evidence.

Run from repository root with backend/.venv/Scripts/python.exe.
Auth bypass is test-only; binds to loopback; AI is disabled to prevent paid calls.
The normal CI E2E path must continue to use migrated PostgreSQL.
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    with TemporaryDirectory(prefix="prepwise-ui-test-") as directory:
        database = Path(directory) / "prepwise_ui_test.db"
        os.environ.update(
            {
                "APP_ENV": "test",
                "DATABASE_URL": "sqlite+pysqlite:///" + database.as_posix(),
                "E2E_AUTH_ENABLED": "true",
                "ASSISTANT_ENABLED": "false",
                "OPENAI_API_KEY": "",
                "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
            }
        )
        import uvicorn
        from sqlalchemy.orm import Session

        from prepwise_api.database import get_engine
        from prepwise_api.main import app
        from prepwise_api.models import Base, User, UserRole
        from prepwise_api.seed import seed_database

        Base.metadata.create_all(get_engine())
        seed_database(get_engine())
        with Session(get_engine()) as session, session.begin():
            session.add(
                User(
                    external_subject="e2e:admin",
                    email="admin.e2e@example.invalid",
                    display_name="E2E Admin",
                    role=UserRole.ADMIN,
                )
            )
        try:
            uvicorn.run(app, host="127.0.0.1", port=8000)
        finally:
            get_engine().dispose()


if __name__ == "__main__":
    main()
