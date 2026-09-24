from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prepwise_api.auth import require_admin
from prepwise_api.database import get_session
from prepwise_api.models import PickupLocation, User
from prepwise_api.schemas import PickupLocationAdminResponse, PickupLocationAdminWrite

router = APIRouter(prefix="/api/admin/pickup-locations", tags=["admin pickup locations"])


@router.get("", response_model=list[PickupLocationAdminResponse])
def list_admin_pickup_locations(
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[PickupLocationAdminResponse]:
    """Return active and inactive pickup locations to admins."""
    locations = session.scalars(select(PickupLocation).order_by(PickupLocation.name)).all()
    return [_admin_pickup_response(location) for location in locations]


@router.post(
    "",
    response_model=PickupLocationAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_pickup_location(
    payload: PickupLocationAdminWrite,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> PickupLocationAdminResponse:
    """Create a validated pickup location."""
    location = PickupLocation(name=payload.name)
    return _save_location(session, location, payload)


@router.patch("/{location_id}", response_model=PickupLocationAdminResponse)
def update_admin_pickup_location(
    location_id: UUID,
    payload: PickupLocationAdminWrite,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> PickupLocationAdminResponse:
    """Replace editable pickup-location fields."""
    location = session.get(PickupLocation, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pickup location not found",
        )
    return _save_location(session, location, payload)


def _save_location(
    session: Session,
    location: PickupLocation,
    payload: PickupLocationAdminWrite,
) -> PickupLocationAdminResponse:
    location.name = payload.name
    location.address_line = payload.address_line
    location.postal_code = payload.postal_code
    location.city = payload.city
    location.active = payload.active
    session.add(location)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pickup location with that name already exists",
        ) from error
    session.refresh(location)
    return _admin_pickup_response(location)


def _admin_pickup_response(location: PickupLocation) -> PickupLocationAdminResponse:
    return PickupLocationAdminResponse(
        id=location.id,
        name=location.name,
        address_line=location.address_line,
        postal_code=location.postal_code,
        city=location.city,
        active=location.active,
    )
