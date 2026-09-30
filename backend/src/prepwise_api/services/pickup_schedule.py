from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from prepwise_api.schemas.pickup import (
    PickupDayResponse,
    PickupOptionsResponse,
    PickupSlot,
    PickupSlotResponse,
)
from prepwise_api.services import ApplicationValidationError

OSLO_TIME_ZONE = ZoneInfo("Europe/Oslo")
SLOT_HOURS: dict[PickupSlot, tuple[int, int]] = {"16-18": (16, 18), "18-20": (18, 20)}


def list_pickup_options(*, now: datetime | None = None) -> PickupOptionsResponse:
    current = now or datetime.now(UTC)
    first_date = current.astimezone(OSLO_TIME_ZONE).date() + timedelta(days=1)
    days = []
    for offset in range(5):
        pickup_date = first_date + timedelta(days=offset)
        slots = [
            PickupSlotResponse(
                id=slot_id,
                start_at=datetime.combine(pickup_date, time(start), OSLO_TIME_ZONE),
                end_at=datetime.combine(pickup_date, time(end), OSLO_TIME_ZONE),
            )
            for slot_id, (start, end) in SLOT_HOURS.items()
        ]
        days.append(PickupDayResponse(date=pickup_date, slots=slots))
    return PickupOptionsResponse(timezone="Europe/Oslo", days=days)


def validate_pickup_selection(
    pickup_date: date, pickup_slot: str, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    for day in list_pickup_options(now=now).days:
        if day.date == pickup_date:
            for slot in day.slots:
                if slot.id == pickup_slot:
                    return slot.start_at.astimezone(UTC), slot.end_at.astimezone(UTC)
    raise ApplicationValidationError("Choose a pickup date and time from the available options")
