from datetime import date

import pytest

from app.engine.time_period_resolver import (
    TimePeriod,
    TimePeriodResolver,
)


def test_daily_periods():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="diário",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 3),
    )

    assert len(periods) == 3

    assert periods[0].period_id == "2027-01-01"
    assert periods[1].period_id == "2027-01-02"
    assert periods[2].period_id == "2027-01-03"


def test_daily_period_dates():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="diário",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 2),
    )

    assert periods[0].start_date == date(2027, 1, 1)
    assert periods[0].end_date == date(2027, 1, 1)

    assert periods[1].start_date == date(2027, 1, 2)
    assert periods[1].end_date == date(2027, 1, 2)


def test_monthly_periods():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
    )

    assert len(periods) == 12

    assert periods[0].period_id == "2027-01"
    assert periods[-1].period_id == "2027-12"


def test_monthly_period_dates():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 3, 31),
    )

    assert periods[0].start_date == date(2027, 1, 1)
    assert periods[0].end_date == date(2027, 1, 31)

    assert periods[1].start_date == date(2027, 2, 1)
    assert periods[1].end_date == date(2027, 2, 28)

    assert periods[2].start_date == date(2027, 3, 1)
    assert periods[2].end_date == date(2027, 3, 31)


def test_leap_year():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="diário",
        start_date=date(2028, 1, 1),
        end_date=date(2028, 12, 31),
    )

    assert len(periods) == 366


def test_monthly_leap_year():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2028, 1, 1),
        end_date=date(2028, 12, 31),
    )

    assert len(periods) == 12

    february = periods[1]

    assert february.period_id == "2028-02"
    assert february.start_date == date(2028, 2, 1)
    assert february.end_date == date(2028, 2, 29)


def test_cross_year_months():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2027, 11, 1),
        end_date=date(2028, 2, 29),
    )

    assert len(periods) == 4

    assert [period.period_id for period in periods] == [
        "2027-11",
        "2027-12",
        "2028-01",
        "2028-02",
    ]


def test_partial_month_horizon():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2027, 1, 15),
        end_date=date(2027, 3, 10),
    )

    assert len(periods) == 3

    assert periods[0].start_date == date(2027, 1, 1)
    assert periods[0].end_date == date(2027, 1, 31)

    assert periods[-1].start_date == date(2027, 3, 1)
    assert periods[-1].end_date == date(2027, 3, 31)


def test_same_day():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="diário",
        start_date=date(2027, 5, 10),
        end_date=date(2027, 5, 10),
    )

    assert len(periods) == 1
    assert periods[0].period_id == "2027-05-10"


def test_same_month():
    resolver = TimePeriodResolver()

    periods = resolver.resolve(
        frequency="mensal",
        start_date=date(2027, 5, 10),
        end_date=date(2027, 5, 20),
    )

    assert len(periods) == 1
    assert periods[0].period_id == "2027-05"


def test_invalid_frequency():
    resolver = TimePeriodResolver()

    with pytest.raises(ValueError, match="Unsupported frequency"):
        resolver.resolve(
            frequency="semanal",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 31),
        )


def test_missing_frequency():
    resolver = TimePeriodResolver()

    with pytest.raises(ValueError, match="Frequency is required"):
        resolver.resolve(
            frequency="",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 31),
        )


def test_invalid_date_range():
    resolver = TimePeriodResolver()

    with pytest.raises(
        ValueError,
        match="start_date must be earlier than or equal to end_date",
    ):
        resolver.resolve(
            frequency="diário",
            start_date=date(2027, 2, 1),
            end_date=date(2027, 1, 1),
        )


def test_invalid_start_date():
    resolver = TimePeriodResolver()

    with pytest.raises(TypeError, match="start_date must be a date"):
        resolver.resolve(
            frequency="diário",
            start_date="2027-01-01",
            end_date=date(2027, 1, 31),
        )


def test_invalid_end_date():
    resolver = TimePeriodResolver()

    with pytest.raises(TypeError, match="end_date must be a date"):
        resolver.resolve(
            frequency="diário",
            start_date=date(2027, 1, 1),
            end_date="2027-01-31",
        )


def test_time_period_is_immutable():
    period = TimePeriod(
        period_id="2027-01-01",
        frequency="diário",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 1),
    )

    with pytest.raises(AttributeError):
        period.period_id = "2027-01-02"
