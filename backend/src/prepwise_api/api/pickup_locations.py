from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from prepwise_api.database import get_session
from prepwise_api.models import PickupLocation
from prepwise_api.schemas import PickupLocationResponse

router = APIRouter(prefix="/api/pickup-locations", tags=["pickup locations"])


@router.get("", response_model=list[PickupLocationResponse])
def list_active_pickup_locations(
    session: Annotated[Session, Depends(get_session)],
) -> list[PickupLocationResponse]:
    """Return active pickup locations from PostgreSQL."""
    locations = session.scalars(
        select(PickupLocation).where(PickupLocation.active.is_(True)).order_by(PickupLocation.name)
    ).all()
    return [_pickup_response(location) for location in locations]


@router.get("/{location_id}", response_model=PickupLocationResponse)
def get_active_pickup_location(
    location_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PickupLocationResponse:
    """Resolve a selectable location and reject missing or inactive choices."""
    location = session.scalar(
        select(PickupLocation).where(
            PickupLocation.id == location_id,
            PickupLocation.active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pickup location not found or inactive",
        )
    return _pickup_response(location)


def _pickup_response(location: PickupLocation) -> PickupLocationResponse:
    return PickupLocationResponse(
        id=location.id,
        name=location.name,
        address_line=location.address_line,
        postal_code=location.postal_code,
        city=location.city,
    )
