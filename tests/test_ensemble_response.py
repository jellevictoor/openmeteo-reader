from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from openmeteo_reader.domain.ensemble_response import parse_ensemble_readings
from openmeteo_reader.domain.models import WeatherReading

VARIABLES = ["temperature_2m", "precipitation"]


def test_computes_min_median_max_across_members_per_variable_per_hour():
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00", "2026-08-20T01:00"],
            "temperature_2m_member01": [10.0, 11.0],
            "temperature_2m_member02": [12.0, 13.0],
            "temperature_2m_member03": [14.0, 9.0],
            "precipitation_member01": [0.0, 1.0],
            "precipitation_member02": [0.5, 3.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings == [
        WeatherReading(
            timestamp=datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
            location="home",
            values={
                "temperature_2m_min": 10.0,
                "temperature_2m_median": 12.0,
                "temperature_2m_max": 14.0,
                "precipitation_min": 0.0,
                "precipitation_median": 0.25,
                "precipitation_max": 0.5,
                "precipitation_total_min": 0.0,
                "precipitation_total_median": 0.25,
                "precipitation_total_max": 0.5,
                "precipitation_total_probability": 0.0,
            },
        ),
        WeatherReading(
            timestamp=datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
            location="home",
            values={
                "temperature_2m_min": 9.0,
                "temperature_2m_median": 11.0,
                "temperature_2m_max": 13.0,
                "precipitation_min": 1.0,
                "precipitation_median": 2.0,
                "precipitation_max": 3.0,
                "precipitation_total_min": 1.0,
                "precipitation_total_median": 2.25,
                "precipitation_total_max": 3.5,
                "precipitation_total_probability": 100.0,
            },
        ),
    ]


def test_omits_a_variable_for_an_hour_where_every_member_is_null():
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00"],
            "temperature_2m_member01": [None],
            "temperature_2m_member02": [None],
            "precipitation_member01": [1.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings == [
        WeatherReading(
            timestamp=datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
            location="home",
            values={
                "precipitation_min": 1.0,
                "precipitation_median": 1.0,
                "precipitation_max": 1.0,
                "precipitation_total_min": 1.0,
                "precipitation_total_median": 1.0,
                "precipitation_total_max": 1.0,
                "precipitation_total_probability": 100.0,
            },
        ),
    ]


def test_returns_no_readings_when_hourly_block_is_missing():
    assert parse_ensemble_readings({}, location="home", variables=VARIABLES, day_zone=UTC) == []


def test_precipitation_total_tracks_each_members_running_total_across_the_day():
    # Regression: two of three members each expect a 6mm shower, just in
    # different hours, so every single hour has a 2-1 dry majority and a median
    # of 0. Summing those hourly medians (the old day-card calculation) gives
    # 0mm for the whole day, even though two-thirds of the ensemble expects a
    # wet day. Tracking each member's own total first fixes that.
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00", "2026-08-20T01:00"],
            "precipitation_member01": [0.0, 6.0],
            "precipitation_member02": [6.0, 0.0],
            "precipitation_member03": [0.0, 0.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings[0].values["precipitation_median"] == 0.0
    assert readings[1].values["precipitation_median"] == 0.0
    assert readings[1].values["precipitation_total_min"] == 0.0
    assert readings[1].values["precipitation_total_median"] == 6.0
    assert readings[1].values["precipitation_total_max"] == 6.0


def test_precipitation_total_resets_at_a_utc_day_boundary():
    raw = {
        "hourly": {
            "time": ["2026-08-20T23:00", "2026-08-21T00:00"],
            "precipitation_member01": [5.0, 2.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings[0].values["precipitation_total_median"] == 5.0
    assert readings[1].values["precipitation_total_median"] == 2.0


def test_pools_members_of_every_model_into_one_ensemble():
    # Asking Open-Meteo for two ensemble models suffixes every column with the
    # model; the control run of each model has no member number at all.
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00"],
            "temperature_2m_icon_seamless_eps": [10.0],
            "temperature_2m_member01_icon_seamless_eps": [11.0],
            "temperature_2m_ecmwf_ifs025_ensemble": [13.0],
            "temperature_2m_member01_ecmwf_ifs025_ensemble": [14.0],
            "precipitation_member01_icon_seamless_eps": [0.0],
            "precipitation_member01_ecmwf_ifs025_ensemble": [2.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    values = readings[0].values
    assert values["temperature_2m_min"] == 10.0
    assert values["temperature_2m_median"] == 12.0
    assert values["temperature_2m_max"] == 14.0
    assert values["precipitation_median"] == 1.0
    assert "temperature_2m_icon_seamless_eps_median" not in values


def test_precipitation_total_resets_at_local_midnight_not_utc_midnight():
    # In Belgian summer time 21:00 UTC is 23:00 local and 22:00 UTC is 00:00 the
    # next local day, so the day's total has to restart there, not at 00:00 UTC.
    raw = {
        "hourly": {
            "time": ["2026-08-20T21:00", "2026-08-20T22:00", "2026-08-20T23:00"],
            "precipitation_member01": [5.0, 2.0, 1.0],
        }
    }

    readings = parse_ensemble_readings(
        raw, location="home", variables=VARIABLES, day_zone=ZoneInfo("Europe/Brussels")
    )

    assert readings[0].values["precipitation_total_median"] == 5.0
    assert readings[1].values["precipitation_total_median"] == 2.0
    assert readings[2].values["precipitation_total_median"] == 3.0
    assert readings[1].timestamp == datetime(2026, 8, 20, 22, 0, tzinfo=UTC)


def test_total_probability_is_the_share_of_members_with_at_least_1mm_so_far_today():
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00", "2026-08-20T01:00"],
            "precipitation_member01": [0.5, 0.6],
            "precipitation_member02": [0.0, 0.0],
            "precipitation_member03": [3.0, 0.0],
            "precipitation_member04": [None, 0.2],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings[0].values["precipitation_total_probability"] == 25.0
    assert readings[1].values["precipitation_total_probability"] == 50.0


def test_negative_precipitation_from_a_member_counts_as_zero():
    # ECMWF members occasionally report -0.1 mm for an hour: a rounding artifact
    # of de-accumulating a running sum. Rain can't be negative, so it counts as
    # dry - otherwise it drags the minimum and the day's total below zero.
    raw = {
        "hourly": {
            "time": ["2026-08-20T00:00", "2026-08-20T01:00"],
            "precipitation_member01": [-0.1, -0.1],
            "precipitation_member02": [0.4, 0.0],
            "temperature_2m_member01": [-3.0, -4.0],
        }
    }

    readings = parse_ensemble_readings(raw, location="home", variables=VARIABLES, day_zone=UTC)

    assert readings[0].values["precipitation_min"] == 0.0
    assert readings[1].values["precipitation_total_min"] == 0.0
    assert readings[1].values["precipitation_total_median"] == 0.2
    # temperatures below zero are real
    assert readings[0].values["temperature_2m_min"] == -3.0
