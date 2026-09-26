from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from prepwise_api.models import PickupLocation
from prepwise_api.schemas import PickupLocationResponse
from prepwise_api.services import ApplicationNotFoundError


def list_active_pickup_locations(session: Session) -> list[PickupLocationResponse]:
    locations = session.scalars(
        select(PickupLocation).where(PickupLocation.active.is_(True)).order_by(PickupLocation.name)
    ).all()
    return [pickup_location_response(location) for location in locations]


def get_active_pickup_location(
    session: Session,
    location_id: UUID,
) -> PickupLocationResponse:
    location = session.scalar(
        select(PickupLocation).where(
            PickupLocation.id == location_id,
            PickupLocation.active.is_(True),
        )
    )
    if location is None:
        raise ApplicationNotFoundError("Pickup location not found or inactive")
    return pickup_location_response(location)


def pickup_location_response(location: PickupLocation) -> PickupLocationResponse:
    return PickupLocationResponse(
        id=location.id,
        name=location.name,
        address_line=location.address_line,
        postal_code=location.postal_code,
        city=location.city,
    )
