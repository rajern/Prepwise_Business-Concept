from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prepwise_api.api.service_errors import raise_service_http_error
from prepwise_api.database import get_session
from prepwise_api.schemas import PickupLocationResponse
from prepwise_api.services import ApplicationServiceError
from prepwise_api.services.pickup_locations import (
    get_active_pickup_location as get_active_pickup_location_service,
)
from prepwise_api.services.pickup_locations import (
    list_active_pickup_locations as list_active_pickup_locations_service,
)

router = APIRouter(prefix="/api/pickup-locations", tags=["pickup locations"])


@router.get("", response_model=list[PickupLocationResponse])
def list_active_pickup_locations(
    session: Annotated[Session, Depends(get_session)],
) -> list[PickupLocationResponse]:
    """Return active pickup locations from PostgreSQL."""
    return list_active_pickup_locations_service(session)


@router.get("/{location_id}", response_model=PickupLocationResponse)
def get_active_pickup_location(
    location_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PickupLocationResponse:
    """Resolve a selectable location and reject missing or inactive choices."""
    try:
        return get_active_pickup_location_service(session, location_id)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
