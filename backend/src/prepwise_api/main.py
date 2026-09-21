from fastapi import FastAPI

from prepwise_api.database import check_database_connection

app = FastAPI(
    title="Prepwise API",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return basic process health for local development."""
    return {"status": "ok"}


@app.get("/health/database", tags=["health"])
def database_health() -> dict[str, str]:
    """Verify that the API can connect to PostgreSQL."""
    check_database_connection()
    return {"status": "ok"}
