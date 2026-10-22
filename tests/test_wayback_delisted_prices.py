from datetime import date
from io import StringIO

import pandas as pd
import pytest

from tools.research.wayback_delisted_prices import fetch_wayback_yahoo_csv_history


class FakeResponse:
    def __init__(self, *, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def test_wayback_fetches_and_date_filters_archived_yahoo_csv():
    cdx = [
        ["timestamp", "original", "statuscode", "length", "mimetype"],
        ["20160102030405", "https://real-chart.finance.yahoo.com/table.csv?s=DEAD", "200", "500", "text/csv"],
    ]
    csv_text = (
        "Date,Open,High,Low,Close,Volume,Adj Close\n"
        "2015-12-31,10,11,9,10.5,1000,10.5\n"
        "2016-01-04,10.5,12,10,11.5,1200,11.5\n"
        "2016-01-05,11.5,12,11,11.8,1300,11.8\n"
    )
    session = FakeSession([FakeResponse(payload=cdx), FakeResponse(text=csv_text)])

    frame = fetch_wayback_yahoo_csv_history(
        session, "DEAD", date(2016, 1, 1), date(2016, 1, 5)
    )

    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    assert frame.index.strftime("%Y-%m-%d").tolist() == ["2016-01-04"]
    assert frame.iloc[0]["Adj Close"] == 11.5
    assert len(session.calls) == 2


def test_wayback_rejects_non_yahoo_snapshot_hosts():
    cdx = [
        ["timestamp", "original", "statuscode", "length", "mimetype"],
        ["20160102030405", "https://attacker.example/table.csv", "200", "9999", "text/csv"],
    ]
    session = FakeSession([FakeResponse(payload=cdx)])

    with pytest.raises(RuntimeError, match="no usable legacy Yahoo CSV"):
        fetch_wayback_yahoo_csv_history(
            session, "DEAD", date(2016, 1, 1), date(2017, 1, 1)
        )
    assert len(session.calls) == 1


def test_wayback_empty_cdx_is_a_clear_nonfatal_provider_error():
    session = FakeSession([FakeResponse(payload=[["timestamp", "original"]])])

    with pytest.raises(RuntimeError, match="no indexed legacy Yahoo CSV"):
        fetch_wayback_yahoo_csv_history(
            session, "DEAD", date(2016, 1, 1), date(2017, 1, 1)
        )
