# -*- coding: utf-8 -*-
from pathlib import Path
import json

import pandas as pd

from tools.research.macro_curve_allocation import target

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "macro_d"


def test_state_map_is_frozen():
    assert target(1.0, -0.2) == {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}
    assert target(-0.2, -0.2) == {"IEF": 0.40, "TLT": 0.30, "SPY": 0.15, "BIL": 0.15}
    assert target(1.0, 0.2) == {"IEF": 0.30, "TLT": 0.20, "BIL": 0.50}
    assert target(-0.2, 0.2) == {"BIL": 1.0}
    assert target(None, 0.2) == {"BIL": 1.0}
    assert target(1.0, None) == {"BIL": 1.0}


def test_pit_files_cover_only_2014_onward():
    for s in ("T10Y3M", "NFCI"):
        d = pd.read_csv(D / f"pit_{s}.csv")
        assert pd.to_datetime(d["vintage_date"]).min() >= pd.Timestamp("2014-01-01")
        assert d["value"].notna().all()
        assert (pd.to_datetime(d["vintage_date"]) <= pd.Timestamp("2026-10-30")).all()


def test_baml_series_is_too_short_and_not_used():
    d = pd.read_csv(D / "BAMLH0A0HYM2.csv")
    assert pd.to_datetime(d.iloc[0, 0]).year >= 2023
    assert len(d) < 1000


def test_declared_prices_have_no_rows_after_cutoff():
    for t in ("SPY", "IEF", "TLT", "BIL"):
        d = pd.read_csv(D / f"{t}.csv")
        dts = pd.to_datetime(d["Date"], utc=True).dt.tz_convert(None).dt.normalize()
        assert dts.max() <= pd.Timestamp("2026-10-30")


def test_nonverified_pit_is_not_claimed_as_primary():
    m = json.loads((D / "manifest.json").read_text(encoding="utf-8"))
    assert m["audit"]["NFCI"]["pit_verified"] is False
    assert m["audit"]["T10Y3M"]["pit_verified"] is False
