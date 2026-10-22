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
    load_membership_history_with_aliases,
    tickers_overlapping,
)
import refresh_sp500_pit_prices as refresh_prices
from low_frequency_atr_execution_validation import attach_execution_returns, load_inputs
from quant_factor_backtest import forward_return_nd
from run_research_ic_sp500_pit_10y import (
    build_market_aligned_adjusted_price_map,
    prepare_adjusted_label_inputs,
)


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
    aliases_path = tmp_path / "aliases.csv"
    aliases_path.write_text(
        "old_ticker,canonical_ticker,cik,source_url,change_type\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        history=history_path,
        aliases=aliases_path,
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



def test_adjusted_return_labels_do_not_change_raw_factor_values():
    snapshot = pd.DataFrame(
        [{
            "Ticker": "AAA",
            "Technical_Date": "2020-01-02",
            "Price": "10.00",
            "Momentum_20D_Pct": "3.25",
        }]
    )
    prices = pd.DataFrame(
        [{
            "Date": "2020-01-02",
            "Ticker": "AAA",
            "Open": "10.0",
            "Close": "10.0",
            "Adj Close": "9.5",
            "Price_Basis": "raw_ohlc_adj_close",
        }]
    )

    adjusted_snapshot, adjusted_prices = prepare_adjusted_label_inputs(snapshot, prices)

    assert adjusted_snapshot.loc[0, "Price"] == "9.50000000"
    assert adjusted_snapshot.loc[0, "Momentum_20D_Pct"] == "3.25"
    assert snapshot.loc[0, "Price"] == "10.00"
    assert adjusted_prices.loc[0, "Close"] == 9.5


def test_adjusted_return_labels_fail_when_adjusted_close_is_missing():
    snapshot = pd.DataFrame(
        [{"Ticker": "AAA", "Technical_Date": "2020-01-02", "Price": "10.0"}]
    )
    prices = pd.DataFrame(
        [{
            "Date": "2020-01-02",
            "Ticker": "AAA",
            "Close": "10.0",
            "Adj Close": "",
            "Price_Basis": "raw_ohlc_adj_close",
        }]
    )

    with pytest.raises(ValueError, match="Adjusted close missing/invalid"):
        prepare_adjusted_label_inputs(snapshot, prices)



def test_execution_validation_uses_adjusted_open_and_close():
    snapshot = pd.DataFrame(
        [{
            "Ticker": "AAA",
            "Scan_Date": "2020-01-03",
            "Technical_Date": "2020-01-02",
            "ATR_Pct": 4.5,
        }]
    )
    prices = pd.DataFrame(
        [
            {"Date": "2020-01-02", "Ticker": "AAA", "Open": 90, "Close": 95, "Adj Open": 81, "Adj Close": 85.5, "Price_Basis": "raw_ohlc_adj_close"},
            {"Date": "2020-01-03", "Ticker": "AAA", "Open": 100, "Close": 110, "Adj Open": 80, "Adj Close": 88, "Price_Basis": "raw_ohlc_adj_close"},
            {"Date": "2020-01-06", "Ticker": "AAA", "Open": 110, "Close": 120, "Adj Open": 86.25, "Adj Close": 90, "Price_Basis": "raw_ohlc_adj_close"},
        ]
    )
    clean_snapshot, by_ticker = load_inputs(snapshot, prices)
    result, audit = attach_execution_returns(clean_snapshot, by_ticker, hold_sessions=2)

    assert audit["rows_valid"] == 1
    assert result.loc[0, "Execution_Return"] == pytest.approx(90 / 80 - 1)
    assert result.loc[0, "Execution_Return"] != pytest.approx(120 / 100 - 1)



def test_missing_stock_bar_does_not_shift_forward_return_horizon():
    prices = pd.DataFrame(
        [
            {"Date": "2020-01-02", "Ticker": "AAA", "Close": 10.0},
            {"Date": "2020-01-06", "Ticker": "AAA", "Close": 12.0},
        ]
    )
    market_dates = ["2020-01-02", "2020-01-03", "2020-01-06"]

    price_map = build_market_aligned_adjusted_price_map(prices, market_dates)

    assert pd.isna(price_map["AAA"].loc[pd.Timestamp("2020-01-03")])
    assert forward_return_nd(price_map["AAA"], "2020-01-02", 10.0, 1) is None
    assert forward_return_nd(price_map["AAA"], "2020-01-02", 10.0, 2) == pytest.approx(0.2)



def test_missing_bulk_ticker_is_retried_singly_and_reported_as_recovered():
    index = pd.to_datetime(["2020-01-02", "2020-01-03"])
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

    def valid_frame(base):
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

    missing_frame = pd.DataFrame(float("nan"), index=index, columns=fields)
    bulk = pd.concat(
        {"AAA": valid_frame(10.0), "BBB": missing_frame},
        axis=1,
    )
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs.copy())
        if kwargs["tickers"] == ["AAA", "BBB"]:
            return bulk
        assert kwargs["tickers"] == ["BBB"]
        assert kwargs["threads"] is False
        return valid_frame(20.0)

    output, diagnostics = refresh_prices.download_historical_prices(
        ["AAA", "BBB"],
        date(2020, 1, 1),
        date(2020, 1, 4),
        batch_size=2,
        retries=1,
        sleeper=lambda _seconds: None,
        downloader=fake_download,
    )

    assert set(output["Ticker"]) == {"AAA", "BBB"}
    assert len(output) == 4
    assert len(calls) == 2
    assert diagnostics == [{
        "ticker": "BBB",
        "status": "recovered",
        "bulk_error": "ticker frame returned no valid raw/adjusted OHLC rows",
        "fallback_attempts": 1,
        "recovery_method": "single_ticker_download",
        "rows": 2,
    }]


def test_unrecoverable_ticker_is_counted_as_a_download_failure():
    index = pd.to_datetime(["2020-01-02", "2020-01-03"])
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing_frame = pd.DataFrame(float("nan"), index=index, columns=fields)
    bulk = pd.concat({"BBB": missing_frame}, axis=1)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs.copy())
        if kwargs["repair"] is True:
            return bulk
        return pd.DataFrame(columns=fields)

    output, diagnostics = refresh_prices.download_historical_prices(
        ["BBB"],
        date(2020, 1, 1),
        date(2020, 1, 4),
        batch_size=1,
        retries=1,
        sleeper=lambda _seconds: None,
        downloader=fake_download,
    )

    assert output.empty
    assert len(calls) == 3
    assert calls[0]["threads"] == 4
    assert all(call["threads"] is False for call in calls[1:])
    assert len(diagnostics) == 1
    assert diagnostics[0]["ticker"] == "BBB"
    assert diagnostics[0]["status"] == "failed"
    assert "no valid raw/adjusted OHLC rows" in diagnostics[0]["bulk_error"]
    assert diagnostics[0]["fallback_attempts"] == 2
    assert diagnostics[0]["recovery_method"] == "single_ticker_download_failed"






def test_ticker_history_api_recovers_symbol_missing_from_download_api():
    index = pd.to_datetime(["2020-01-02", "2020-01-03"])
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing_frame = pd.DataFrame(float("nan"), index=index, columns=fields)
    bulk = pd.concat({"AAA": missing_frame}, axis=1)
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs.copy())
        if kwargs["repair"] is True:
            return bulk
        return pd.DataFrame(columns=fields)

    history_calls = []

    def fake_history(ticker, start, end):
        history_calls.append((ticker, start, end))
        return pd.DataFrame(
            {
                "Open": [10.0, 11.0],
                "High": [12.0, 13.0],
                "Low": [9.0, 10.0],
                "Close": [11.0, 12.0],
                "Adj Close": [10.5, 11.5],
                "Volume": [100, 110],
            },
            index=index,
        )

    output, diagnostics = refresh_prices.download_historical_prices(
        ["AAA"],
        date(2020, 1, 1),
        date(2020, 1, 4),
        batch_size=1,
        retries=1,
        sleeper=lambda _seconds: None,
        downloader=fake_download,
        history_fetcher=fake_history,
    )

    assert len(calls) == 3
    assert history_calls == [("AAA", date(2020, 1, 1), date(2020, 1, 4))]
    assert len(output) == 2
    assert set(output["Ticker"]) == {"AAA"}
    assert diagnostics == [{
        "ticker": "AAA",
        "status": "recovered",
        "bulk_error": "ticker frame returned no valid raw/adjusted OHLC rows",
        "fallback_attempts": 3,
        "recovery_method": "ticker_history",
        "rows": 2,
    }]


def write_aliases(path: Path, rows: str) -> Path:
    path.write_text(
        "old_ticker,canonical_ticker,cik,source_url,change_type\n" + rows,
        encoding="utf-8",
    )
    return path


def test_alias_loader_canonicalizes_same_security_symbols(tmp_path):
    membership = write_membership(
        tmp_path / "history.csv",
        "OLD,0000000001,Old Name,technology,2020-01-01,2020-12-31,2020-01-01\n"
        "NEW,1,New Name,technology,2020-12-01,,2020-12-01\n",
    )
    aliases = write_aliases(
        tmp_path / "aliases.csv",
        "OLD,NEW,1,https://example.com/issuer,ticker/name change\n",
    )
    usage = {}

    history = load_membership_history_with_aliases(membership, aliases, alias_usage=usage)

    assert set(history) == {"NEW"}
    assert is_member_on("NEW", date(2020, 12, 15), history)
    assert active_tickers_on(date(2020, 12, 15), history) == {"NEW"}
    assert usage["registry_rows"] == 1
    assert usage["applied_source_symbols"] == [("OLD", "NEW")]


def test_alias_loader_guards_reused_ticker_by_cik(tmp_path):
    membership = write_membership(
        tmp_path / "history.csv",
        "ARNC,0000004281,Former issuer,industrials,2016-01-01,2020-01-01,2016-01-01\n"
        "ARNC,0000182322,Reused symbol issuer,industrials,2020-01-01,,2020-01-01\n",
    )
    aliases = write_aliases(
        tmp_path / "aliases.csv",
        "ARNC,HWM,4281,https://example.com/issuer,ticker reused by another CIK\n",
    )

    history = load_membership_history_with_aliases(membership, aliases)

    assert "HWM" in history
    assert "ARNC" in history
    assert is_member_on("HWM", date(2019, 6, 1), history)
    assert not is_member_on("HWM", date(2021, 1, 1), history)
    assert is_member_on("ARNC", date(2021, 1, 1), history)


def test_vendored_ticker_alias_registry_matches_historical_ciks():
    usage = {}
    history = load_membership_history_with_aliases(
        refresh_prices.DEFAULT_HISTORY,
        refresh_prices.DEFAULT_TICKER_ALIASES,
        alias_usage=usage,
    )

    assert usage["registry_rows"] == 31
    assert usage["applied_source_symbol_count"] == 31
    assert refresh_prices.git_blob_sha(refresh_prices.DEFAULT_TICKER_ALIASES) == (
        refresh_prices.PINNED_TICKER_ALIAS_BLOB_SHA
    )
    assert "COR" in history
    assert "GAP" in history
    assert "BKNG" in history
    assert "BKR" in history
    assert "RVTY" in history
    assert "PARA" in history
    assert "ELV" in history
    assert "HWM" in history
    assert "MRSH" in history
