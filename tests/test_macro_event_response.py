# -*- coding: utf-8 -*-
"""Tests for official macro event feasibility audit."""
import json
from pathlib import Path

import pandas as pd
import pytest

from tools.research.macro_event_response import (
    START, align, audit, load_offline, parse_bls, parse_embargo, parse_fomc,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "macro_event_response"


def test_parse_bls_dates_and_date_only_default():
    html = '<a href="../../news.release/archives/cpi_10132020.htm">Sep 2020</a>'
    e = parse_bls(html, "cpi")[0]
    assert e["event_id"] == "cpi_2020-10-13"
    assert e["publication_time"] is None
    assert e["time_type"] == "date_only"


def test_parse_embargo_2021_and_2026_edt():
    a = parse_embargo("Transmission of material in this release is embargoed until 8:30 a.m. (ET) on Wednesday, January 13, 2021.")
    b = parse_embargo("Transmission of material in this release is embargoed until 8:30 a.m. (ET) on Tuesday, January 13, 2026.")
    assert a["embargo_until_utc"].startswith("2021-01-13T13:30")
    assert b["embargo_until_utc"].startswith("2026-01-13T13:30")
    assert a["time_type"] == "official_embargo_until"


def test_parse_embargo_2021_employment_and_dst():
    a = parse_embargo("embargoed until 8:30 a.m. (ET) on Friday, January 8, 2021.")
    assert a["embargo_until_utc"].startswith("2021-01-08T13:30")
    b = parse_embargo("embargoed until 8:30 a.m. (ET) on Friday, January 9, 2026.")
    assert b["embargo_until_utc"].startswith("2026-01-09T13:30")


def test_parse_fomc_old_and_new_links():
    old = '<a href="/newsevents/press/monetary/20070131a.htm">Statement</a>'
    new = '<a href="/newsevents/pressreleases/monetary20260128a.htm">Statement</a>'
    a = parse_fomc(old); b = parse_fomc(new)
    assert a[0]["event_id"] == "fomc_2007-01-31"
    assert b[0]["publication_time"] == "14:00:00"


def test_alignment_preopen_same_session_and_afternoon_next():
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]))
    bls = {"publication_date": "2024-01-03", "publication_time": "08:30:00"}
    fomc = {"publication_date": "2024-01-03", "publication_time": "14:00:00"}
    assert align(bls, sessions) == pd.Timestamp("2024-01-03")
    assert align(fomc, sessions) == pd.Timestamp("2024-01-04")


def test_weekend_alignment():
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-05", "2024-01-08"]))
    e = {"publication_date": "2024-01-06", "publication_time": "08:30:00"}
    assert align(e, sessions) == pd.Timestamp("2024-01-08")


def test_audit_marks_missing_bls_years_blocked():
    events = [{"event_id": "cpi_x", "event_type": "cpi", "publication_date": "2024-01-01"},
              {"event_id": "empsit_x", "event_type": "empsit", "publication_date": "2024-01-01"},
              {"event_id": "fomc_x", "event_type": "fomc", "publication_date": "2024-01-01"}]
    a = audit(events, None)
    assert a["status"] == "DATA_BLOCKED"
    assert a["data_sufficient"] is False
    assert 2021 in a["missing_years"]["cpi"]


def test_committed_audit_is_blocked_and_has_no_study():
    a = json.loads((OUT / "audit.json").read_text())
    assert a["study_status"] == "NOT_RUN_DATA_BLOCKED"
    assert a["audit"]["data_sufficient"] is False
    assert not (OUT / "event_study.csv").exists()
    ev = pd.read_csv(OUT / "events.csv")
    assert {"event_id", "official_source", "official_source_url", "publication_time_utc"} <= set(ev.columns)
    assert len(ev) == 500
    assert ev.event_id.is_unique


def test_offline_import_validates_domain_and_hash(tmp_path):
    html = '<a href="../../news.release/archives/cpi_01132021.htm">CPI</a>'
    (tmp_path / "cpi.html").write_text(html, encoding="utf-8")
    manifest = {"files": [{"family": "cpi", "url": "https://www.bls.gov/bls/news-release/cpi.htm",
                           "path": "cpi.html"}]}
    (tmp_path / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
    events, sources = load_offline(tmp_path)
    assert events[0]["event_id"] == "cpi_2021-01-13"
    assert sources["offline"]["status"] == "OFFLINE_IMPORT"
    bad = {"files": [{"family": "cpi", "url": "https://example.com/cpi", "path": "cpi.html"}]}
    (tmp_path / "manifest.json").write_text(__import__("json").dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_offline(tmp_path)
