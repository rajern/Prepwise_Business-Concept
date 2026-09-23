from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prepwise_api.api import meals_router, users_router
from prepwise_api.config import get_settings
from prepwise_api.database import check_database_connection

settings = get_settings()

app = FastAPI(
    title="Prepwise API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(meals_router)
app.include_router(users_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return basic process health for local development."""
    return {"status": "ok"}


@app.get("/health/database", tags=["health"])
def database_health() -> dict[str, str]:
    """Verify that the API can connect to PostgreSQL."""
    check_database_connection()
    return {"status": "ok"}
