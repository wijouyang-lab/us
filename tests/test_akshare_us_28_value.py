import pytest
import pandas as pd
from tools.research.akshare_us_28_coverage import _shares_check


def shares(period="2026-10-01", value=1000):
    return {"status": "AVAILABLE", "shares": value, "period_end": period,
            "accession": "x", "form": "10-Q"}


def test_shares_check_accepts_matching_current_cap():
    r = _shares_check(10.0, 10_000.0, shares())
    assert r["value_input_ready"] is True
    assert r["status"] == "VALUE_INPUT_READY"
    assert r["market_cap_ratio"] == 1.0


def test_shares_check_rejects_stale_disclosure():
    r = _shares_check(10.0, 10_000.0, shares(period="2015-01-01"))
    assert r["value_input_ready"] is False
    assert r["status"] == "SHARES_NOT_CURRENT"


def test_shares_check_rejects_value_or_unit_mismatch():
    r = _shares_check(10.0, 25_000.0, shares())
    assert r["value_input_ready"] is False
    assert r["status"] == "MARKET_CAP_UNIT_OR_VALUE_MISMATCH"


def test_shares_check_missing_disclosure_is_blocked():
    r = _shares_check(10.0, 10_000.0, None)
    assert r["value_input_ready"] is False
    assert r["status"] == "SHARES_DISCLOSURE_MISSING"
