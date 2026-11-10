# -*- coding: utf-8 -*-
"""Tests for canonical event timestamps and dedupe."""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from event_data import Event, dedupe, next_trading_session  # noqa: E402


def ev(i="e1", **kw):
    base = dict(event_id=i, ticker="AAA", cik="0000000001", event_type="filing",
                event_subtype="10-Q", source="SEC", published_at="2024-01-02T21:30:00Z",
                event_date="2024-01-02", effective_date=None, period_end="2023-12-31",
                value=None, previous_value=None, revised_value=None,
                source_confidence="official", timestamp_confidence="official_acceptance_time_not_first_public",
                pit_eligible=False, evidence_note="test")
    base.update(kw)
    return Event(**base)


def test_after_close_moves_to_next_session():
    cal = list(pd.bdate_range("2024-01-02", periods=5))
    assert next_trading_session("2024-01-02T21:30:00Z", cal) == "2024-01-03"


def test_weekend_moves_to_next_session():
    cal = list(pd.bdate_range("2024-01-05", periods=5))
    assert next_trading_session("2024-01-06T15:00:00Z", cal) == "2024-01-08"


def test_naive_timestamp_rejected():
    try:
        next_trading_session("2024-01-02T21:30:00", list(pd.bdate_range("2024-01-02", periods=3)))
    except ValueError:
        pass
    else:
        raise AssertionError("naive timestamp accepted")


def test_duplicate_event_id_deduped():
    assert len(dedupe([ev("e1"), ev("e1"), ev("e2")])) == 2


def test_event_pit_default_false():
    assert ev().pit_eligible is False
