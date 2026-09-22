from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from prepwise_api.config import get_settings


def database_connect_args(app_env: str) -> dict[str, str]:
    """Require PostgreSQL TLS in production without changing local or test connections."""
    return {"sslmode": "require"} if app_env == "production" else {}


@lru_cache
def get_engine() -> Engine:
    """Create the shared SQLAlchemy engine from environment configuration."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=database_connect_args(settings.app_env),
    )


def get_session() -> Iterator[Session]:
    """Yield one database session for the lifetime of an API request."""
    with Session(get_engine()) as session:
        yield session


def check_database_connection() -> None:
    """Raise if PostgreSQL cannot execute a minimal query."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
