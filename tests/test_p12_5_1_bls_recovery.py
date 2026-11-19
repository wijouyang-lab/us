from datetime import date

import pandas as pd

from tools.research.macro_event_response import parse_embargo
from tools.research.bls_alfred_recovery import initial_events


def test_embargo_winter_is_est():
    out = parse_embargo("Transmission of material in this release is embargoed until 8:30 a.m. (ET) on Thursday, January 11, 2024.")
    assert out["embargo_time"] == "08:30:00"
    assert out["embargo_until_utc"].startswith("2024-01-11T13:30:00")


def test_embargo_summer_is_edt():
    out = parse_embargo("embargoed until 8:30 a.m. (ET) on Thursday, July 11, 2024.")
    assert out["embargo_until_utc"].startswith("2024-07-11T12:30:00")


def test_date_only_has_no_inferred_time():
    assert parse_embargo("Release date: January 11, 2024") is None


def test_reference_period_is_not_release_date(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("observation_date,SERIES_20240111,SERIES_20240213\n2023-12-01,100,100\n2024-01-01,,101\n", encoding="utf-8")
    e = initial_events(p, "test")
    first = e[e.reference_period == "2024-01"].iloc[0]
    assert first.release_date == "2024-02-13"
    assert first.reference_period != first.release_date


def test_first_vintage_is_not_overwritten_by_revision(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("observation_date,SERIES_20240111,SERIES_20240213\n2023-12-01,100,102\n", encoding="utf-8")
    e = initial_events(p, "test")
    assert e.iloc[0].initial_value == 100
    assert e.iloc[0].release_date == "2024-01-11"
