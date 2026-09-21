from fastapi import FastAPI

app = FastAPI(
    title="Prepwise API",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return basic process health for local development."""
    return {"status": "ok"}
