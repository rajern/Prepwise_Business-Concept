"""Prepwise API package."""

from prepwise_api.telemetry import configure_telemetry

# Package initialisation runs before FastAPI is imported, which lets the Azure Monitor
# distribution install its FastAPI import hook in production.
configure_telemetry()
