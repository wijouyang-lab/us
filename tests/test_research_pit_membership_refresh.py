from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from pit_membership import (
    active_tickers_on,
    approximate_date_counts,
    is_member_on,
    load_membership_history,
    tickers_overlapping,
)
import refresh_sp500_pit_prices as refresh_prices


def write_membership(path: Path, rows: str) -> Path:
    path.write_text(
        "symbol,cik,name,sector,date_added,date_removed,created_at\n" + rows,
        encoding="utf-8",
    )
    return path


def test_membership_effective_dates_and_approximation_are_explicit(tmp_path):
    source = write_membership(
        tmp_path / "history.csv",
        "AAA,1,Alpha,technology,2020-01-01*,2020-01-03*,2020-01-01\n",
    )
    history = load_membership_history(source)

    assert is_member_on("aaa", date(2020, 1, 1), history)
    assert is_member_on("AAA", date(2020, 1, 2), history)
    assert not is_member_on("AAA", date(2020, 1, 3), history)
    assert approximate_date_counts(history) == {
        "membership_intervals": 1,
        "approximate_date_added": 1,
        "approximate_date_removed": 1,
    }


def test_repeated_ticker_keeps_separate_membership_intervals(tmp_path):
    source = write_membership(
        tmp_path / "history.csv",
        "AAA,1,Alpha,technology,2016-01-01,2018-01-01,2016-01-01\n"
        "AAA,1,Alpha,technology,2020-01-01,,2020-01-01\n"
        "BBB,2,Beta,finance,2021-01-01,,2021-01-01\n",
    )
    history = load_membership_history(source)

    assert not is_member_on("AAA", date(2019, 6, 1), history)
    assert is_member_on("AAA", date(2017, 1, 1), history)
    assert is_member_on("AAA", date(2022, 1, 1), history)
    assert active_tickers_on(date(2021, 6, 1), history) == {"AAA", "BBB"}
    assert tickers_overlapping(date(2019, 1, 1), date(2020, 12, 31), history) == {"AAA"}


def test_invalid_membership_dates_fail_closed(tmp_path):
    source = write_membership(
        tmp_path / "history.csv",
        "AAA,1,Alpha,technology,2020-01-03,2020-01-01,2020-01-01\n",
    )
    with pytest.raises(ValueError, match="date_removed must be later"):
        load_membership_history(source)


def test_price_ticker_mapping_and_adjusted_bar_normalization():
    assert refresh_prices.yahoo_symbol("BRK.B") == "BRK-B"

    frame = pd.DataFrame(
        {
            "Open": [10.0, 0.0],
            "High": [11.0, 12.0],
            "Low": [9.0, 8.0],
            "Close": [10.5, 0.0],
            "Adj Close": [10.0, 0.0],
            "Volume": [100.0, 200.0],
        },
        index=pd.to_datetime(["2020-01-02", "2020-01-03"]),
    )
    rows = refresh_prices._records_for_symbol(frame, "BRK.B", date(2020, 1, 3), date(2020, 1, 1))

    assert len(rows) == 1
    assert rows[0]["Ticker"] == "BRK.B"
    assert rows[0]["Close"] == 10.5
    assert rows[0]["Adj Close"] == 10.0
    assert rows[0]["Open"] == 10.0
    assert rows[0]["Adj Open"] == pytest.approx(10.0 * 10.0 / 10.5)
    assert rows[0]["Price_Basis"] == "raw_ohlc_adj_close"


def test_batched_download_preserves_canonical_ticker_names():
    index = pd.to_datetime(["2020-01-02", "2020-01-03"])
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

    def rows(base):
        return pd.DataFrame(
            {
                "Open": [base, base + 1],
                "High": [base + 2, base + 3],
                "Low": [base - 1, base],
                "Close": [base + 0.5, base + 1.5],
                "Adj Close": [base + 0.25, base + 1.25],
                "Volume": [100, 110],
            },
            index=index,
        )[fields]

    raw = pd.concat({"AAA": rows(10.0), "BRK-B": rows(20.0)}, axis=1)

    def fake_download(**kwargs):
        assert kwargs["auto_adjust"] is False
        assert kwargs["start"] == "2020-01-01"
        assert kwargs["end"] == "2020-01-04"
        return raw

    output, failures = refresh_prices.download_historical_prices(
        ["AAA", "BRK.B"], date(2020, 1, 1), date(2020, 1, 4),
        batch_size=2, retries=1, sleeper=lambda _seconds: None, downloader=fake_download,
    )

    assert failures == []
    assert set(output["Ticker"]) == {"AAA", "BRK.B"}
    assert len(output) == 4
    assert set(output["Price_Basis"]) == {"raw_ohlc_adj_close"}
    assert (output["Adj Close"] < output["Close"]).all()


def test_member_session_coverage_detects_missing_historical_constituents(tmp_path):
    source = write_membership(
        tmp_path / "history.csv",
        "AAA,1,Alpha,technology,2020-01-01,,2020-01-01\n"
        "BBB,2,Beta,finance,2020-01-01,,2020-01-01\n",
    )
    history = load_membership_history(source)
    dates = [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6)]
    prices = pd.DataFrame(
        [
            {"Date": day.isoformat(), "Ticker": ticker}
            for day in dates for ticker in ["AAA"]
        ]
    )
    coverage = refresh_prices.calculate_member_session_coverage(
        history, prices, dates, date(2020, 1, 1), date(2020, 1, 6)
    )

    assert coverage["expected_member_session_bars"] == 6
    assert coverage["observed_member_session_bars"] == 3
    assert coverage["member_bar_coverage"] == pytest.approx(0.5)
    assert coverage["ticker_coverage"] == pytest.approx(0.5)
    assert {row["ticker"] for row in coverage["low_coverage_tickers"]} == {"BBB"}


def test_refresh_failure_preserves_prior_price_inputs(tmp_path, monkeypatch):
    history_path = write_membership(
        tmp_path / "history.csv",
        "AAA,1,Alpha,technology,2020-01-01,,2020-01-01\n"
        "BBB,2,Beta,finance,2020-01-01,,2020-01-01\n",
    )
    stocks_path = tmp_path / "stocks.csv"
    spy_path = tmp_path / "spy.csv"
    audit_path = tmp_path / "audit.json"
    stocks_path.write_text("previous stock input\n", encoding="utf-8")
    spy_path.write_text("previous spy input\n", encoding="utf-8")
    dates = ["2020-01-02", "2020-01-03", "2020-01-06"]
    rows = []
    for day in dates:
        rows.append({"Date": day, "Ticker": "AAA", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Adj Open": 9.9, "Adj High": 10.89, "Adj Low": 8.91, "Adj Close": 9.9, "Volume": 10, "Price_Basis": "raw_ohlc_adj_close"})
        rows.append({"Date": day, "Ticker": "SPY", "Open": 100, "High": 101, "Low": 99, "Close": 100, "Adj Open": 99, "Adj High": 99.99, "Adj Low": 98.01, "Adj Close": 99, "Volume": 10, "Price_Basis": "raw_ohlc_adj_close"})
    downloaded = pd.DataFrame(rows, columns=refresh_prices.PRICE_COLUMNS)

    monkeypatch.setattr(refresh_prices, "download_historical_prices", lambda *a, **k: (downloaded, []))
    args = SimpleNamespace(
        history=history_path,
        stocks=stocks_path,
        spy=spy_path,
        audit=audit_path,
        analysis_start=date(2020, 1, 1),
        cutoff_date=date(2020, 1, 6),
        warmup_days=120,
        batch_size=30,
        min_member_bar_coverage=0.95,
        min_ticker_coverage=0.90,
        max_spy_staleness_days=4,
    )

    with pytest.raises(SystemExit, match="existing research price inputs were preserved"):
        refresh_prices.refresh(args)

    assert stocks_path.read_text(encoding="utf-8") == "previous stock input\n"
    assert spy_path.read_text(encoding="utf-8") == "previous spy input\n"
    report = json.loads(audit_path.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["coverage"]["member_bar_coverage"] == pytest.approx(0.5)

def test_vendored_membership_source_hash_is_pinned():
    from refresh_sp500_pit_prices import (
        DEFAULT_HISTORY,
        PINNED_MEMBERSHIP_BLOB_SHA,
        git_blob_sha,
    )

    assert git_blob_sha(DEFAULT_HISTORY) == PINNED_MEMBERSHIP_BLOB_SHA
