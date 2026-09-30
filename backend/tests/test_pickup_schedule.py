from datetime import UTC, date, datetime

import pytest

from prepwise_api.services import ApplicationValidationError
from prepwise_api.services.pickup_schedule import list_pickup_options, validate_pickup_selection


def test_pickup_options_include_weekend_and_start_tomorrow_in_oslo() -> None:
    options = list_pickup_options(now=datetime(2026, 10, 2, 22, 30, tzinfo=UTC))
    assert [day.date for day in options.days] == [
        date(2026, 10, 4),
        date(2026, 10, 5),
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
    ]
    assert options.timezone == "Europe/Oslo"
    assert [slot.id for slot in options.days[0].slots] == ["16-18", "18-20"]


def test_pickup_windows_follow_oslo_daylight_saving_transition() -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    before, _ = validate_pickup_selection(date(2026, 10, 24), "16-18", now=now)
    after, end = validate_pickup_selection(date(2026, 10, 25), "18-20", now=now)
    assert before == datetime(2026, 10, 24, 14, tzinfo=UTC)
    assert after == datetime(2026, 10, 25, 17, tzinfo=UTC)
    assert end == datetime(2026, 10, 25, 19, tzinfo=UTC)


@pytest.mark.parametrize(
    "pickup_date,slot",
    [
        (date(2026, 9, 30), "16-18"),
        (date(2026, 10, 6), "16-18"),
        (date(2026, 10, 1), "12-14"),
    ],
)
def test_pickup_selection_rejects_today_out_of_range_or_fabricated_slot(
    pickup_date: date,
    slot: str,
) -> None:
    with pytest.raises(ApplicationValidationError):
        validate_pickup_selection(pickup_date, slot, now=datetime(2026, 9, 30, 12, tzinfo=UTC))
