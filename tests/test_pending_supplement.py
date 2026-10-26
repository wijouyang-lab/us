# -*- coding: utf-8 -*-
"""Regression tests for Pending -> trade_history ingestion (Task A/B).

The production function lives inside review.py, which has top-level network
side effects.  These tests extract the function AST and execute it with
virtual CSVs and stubbed market/ledger dependencies only.
"""

import ast
import datetime as dt
import os
import re
import glob
from pathlib import Path

import pandas as pd
import pytest

from pending_csv import PendingCsvError, read_pending_csv


TRADE_COLUMNS = ["Date", "Ticker", "Tag", "Price", "Close_Price", "Status", "Stop_Loss"]
TARGET_DATE = "2026-10-20"


def _load_supplement(tmp_path):
    source = Path(__file__).resolve().parents[1] / "review.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "supplement_us_stocks_from_pending"
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, "<supplement>", "exec"), ns)

    def safe_float(v, default=None):
        try:
            return float(str(v).replace("$", "").replace(",", ""))
        except Exception:
            return default

    def clean_text(v, default=""):
        return str(v if v not in (None, "") else default)

    def fmt_price(v):
        return "" if v is None else f"{float(v):.2f}"

    def resolve_ticker(t, n=""):
        return str(t or "").strip().upper()

    # Use the production implementation, not a second hand-written copy.
    find_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "find_existing_record"
    )
    find_module = ast.Module(body=[find_node], type_ignores=[])
    ast.fix_missing_locations(find_module)
    find_ns = {
        "pd": pd,
        "normalize_date": lambda value: pd.to_datetime(value, errors="coerce"),
        "clean_text": clean_text,
    }
    exec(compile(find_module, "<find-existing-record>", "exec"), find_ns)
    find_existing_record = find_ns["find_existing_record"]

    def load_trade_history():
        path = Path("trade_history.csv")
        if not path.exists():
            return pd.DataFrame(columns=TRADE_COLUMNS)
        d = pd.read_csv(path, dtype=str, keep_default_na=False)
        if "Date" in d.columns:
            d["Date"] = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        return d

    def fake_download_ohlc_safe(tickers, period="10d", start=None, end=None):
        ns["DOWNLOAD_CALLS"].append({
            "tickers": list(tickers), "period": period,
            "start": start, "end": end,
        })
        return None, None

    ns.update({
        "glob": glob,
        "os": os,
        "re": re,
        "datetime": dt,
        "pd": pd,
        "TRADE_COLUMNS": TRADE_COLUMNS,
        "TRADE_HISTORY": "trade_history.csv",
        "ensure_trade_history_columns": lambda: None,
        "load_trade_history": load_trade_history,
        "resolve_ticker": resolve_ticker,
        "is_probable_us_ticker": lambda t: bool(t),
        "download_ohlc_safe": fake_download_ohlc_safe,
        "get_exact_date_ohlc": lambda hist, ticker, target: ns["OHLC"].get((ticker, target)),
        "find_existing_record": find_existing_record,
        "today_us_str": lambda: TARGET_DATE,
        "get_live_quote_bootstrap": lambda ticker: (None, None),
        "safe_float": safe_float,
        "clean_text": clean_text,
        "recalibrate_stop_loss": lambda stop, ref, op: stop,
        "fmt_price": fmt_price,
        "read_pending_csv": read_pending_csv,
        "PendingCsvError": PendingCsvError,
        "get_us_time": lambda: dt.datetime(2026, 10, 20, 9, 0),
        "OHLC": {},
        "DOWNLOAD_CALLS": [],
    })
    return ns["supplement_us_stocks_from_pending"], ns


def _write_pending(tmp_path, rows, name="us_stocks_pending_20261020.csv"):
    path = tmp_path / name
    header = ["Date", "Ticker", "Tag", "Name", "Scan_Ref_Price", "Stop_Loss"]
    lines = [",".join(header)]
    lines.extend(",".join(str(r.get(h, "")) for h in header) for r in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rows(*tickers):
    return [
        {
            "Date": TARGET_DATE,
            "Ticker": t,
            "Tag": "Core_Dragon",
            "Name": t + " Inc",
            "Scan_Ref_Price": "100",
            "Stop_Loss": "$95",
        }
        for t in tickers
    ]


def _trade_rows():
    path = Path("trade_history.csv")
    if not path.exists():
        return []
    return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")


def test_both_prices_complete_is_persisted_and_processed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA"))
    ns["OHLC"][("AAA", TARGET_DATE)] = {"open": "100", "close": "105"}

    result = fn()
    assert result["incomplete_files"] == []
    assert not path.exists() and (tmp_path / (path.name + ".processed")).exists()
    rows = _trade_rows()
    assert len(rows) == 1
    assert rows[0]["Ticker"] == "AAA"
    assert rows[0]["Price"] == "100.00"
    assert float(rows[0]["Close_Price"]) == 105.0
    assert rows[0]["Status"] == "Active"


@pytest.mark.parametrize("ohlc,missing", [
    ({"close": "105"}, ["Open"]),
    ({"open": "100"}, ["Close"]),
    ({}, ["Open", "Close"]),
])
def test_missing_open_close_or_both_keeps_pending_and_no_active_row(tmp_path, monkeypatch, ohlc, missing):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA"))
    ns["OHLC"][("AAA", TARGET_DATE)] = ohlc

    result = fn()
    assert result["failed_files"] == []
    assert result["incomplete_files"] == [path.name]
    assert result["incomplete_details"] == [{
        "file": path.name,
        "target_date": TARGET_DATE,
        "ticker": "AAA",
        "missing": missing,
    }]
    assert path.exists() and not (tmp_path / (path.name + ".processed")).exists()
    assert _trade_rows() == []


def test_partial_file_success_then_retry_without_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA", "BBB"))
    ns["OHLC"][("AAA", TARGET_DATE)] = {"open": "100", "close": "105"}
    ns["OHLC"][("BBB", TARGET_DATE)] = {"open": "200"}

    first = fn()
    assert first["incomplete_files"] == [path.name]
    assert [r["Ticker"] for r in _trade_rows()] == ["AAA"]
    assert path.exists()

    # Market data arrives for BBB; retry must not duplicate AAA.
    ns["OHLC"][("BBB", TARGET_DATE)] = {"open": "200", "close": "210"}
    second = fn()
    assert second["failed_files"] == [] and second["incomplete_files"] == []
    assert not path.exists() and (tmp_path / (path.name + ".processed")).exists()
    rows = _trade_rows()
    assert [r["Ticker"] for r in rows].count("AAA") == 1
    assert [r["Ticker"] for r in rows].count("BBB") == 1


def test_retry_after_all_missing_recovers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA"))
    first = fn()
    assert first["incomplete_files"] == [path.name]
    assert _trade_rows() == []

    ns["OHLC"][("AAA", TARGET_DATE)] = {"open": "100", "close": "101"}
    second = fn()
    assert second["incomplete_files"] == []
    assert len(_trade_rows()) == 1


def test_corrupt_csv_is_failure_not_processed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = tmp_path / "us_stocks_pending_20261020.csv"
    path.write_text("Date,Ticker,Tag\n2026-10-20,AAA\n", encoding="utf-8")

    result = fn()
    assert result["failed_files"] == [path.name]
    assert result["incomplete_files"] == []
    assert path.exists() and not (tmp_path / (path.name + ".processed")).exists()
    assert _trade_rows() == []

    # Fix the file and retry: the event can be recovered.
    path.write_text(
        "Date,Ticker,Tag,Name,Scan_Ref_Price,Stop_Loss\n"
        "2026-10-20,AAA,Core_Dragon,AAA Inc,100,$95\n",
        encoding="utf-8",
    )
    ns["OHLC"][("AAA", TARGET_DATE)] = {"open": "100", "close": "105"}
    retry = fn()
    assert retry["failed_files"] == [] and retry["incomplete_files"] == []
    assert not path.exists() and (tmp_path / (path.name + ".processed")).exists()
    assert len(_trade_rows()) == 1


@pytest.mark.parametrize("bad_date", ["2026-10-19", "", "not-a-date"])
def test_date_mismatch_fails_closed_and_keeps_pending(tmp_path, monkeypatch, bad_date):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA"))
    path.write_text(
        "Date,Ticker,Tag,Name,Scan_Ref_Price,Stop_Loss\n"
        f"{bad_date},AAA,Core_Dragon,AAA Inc,100,$95\n",
        encoding="utf-8",
    )
    # If the code attempted to use the filename date despite the row mismatch,
    # market data would be available; the file must fail before reaching that point.
    ns["OHLC"][( "AAA", TARGET_DATE)] = {"open": "100", "close": "105"}
    ensure_calls = []
    ns["ensure_trade_history_columns"] = lambda: ensure_calls.append(True)

    result = fn()

    assert result["failed_files"] == [path.name]
    assert result["incomplete_files"] == []
    assert ensure_calls == []
    assert path.exists()
    assert not (tmp_path / (path.name + ".processed")).exists()
    assert _trade_rows() == []


def test_one_mismatched_row_rejects_entire_pending_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = _write_pending(tmp_path, _rows("AAA", "BBB"))
    path.write_text(
        "Date,Ticker,Tag,Name,Scan_Ref_Price,Stop_Loss\n"
        "2026-10-20,AAA,Core_Dragon,AAA Inc,100,$95\n"
        "2026-10-19,BBB,Core_Dragon,BBB Inc,100,$95\n",
        encoding="utf-8",
    )
    ns["OHLC"][( "AAA", TARGET_DATE)] = {"open": "100", "close": "105"}
    ns["OHLC"][( "BBB", TARGET_DATE)] = {"open": "100", "close": "105"}
    ensure_calls = []
    ns["ensure_trade_history_columns"] = lambda: ensure_calls.append(True)

    result = fn()

    assert result["failed_files"] == [path.name]
    assert ensure_calls == []
    assert path.exists() and not (tmp_path / (path.name + ".processed")).exists()
    # Even the valid AAA row must not be partially written.
    assert _trade_rows() == []


def test_data_row_without_date_column_fails_closed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = tmp_path / "us_stocks_pending_20261020.csv"
    path.write_text(
        "Ticker,Tag,Name,Scan_Ref_Price,Stop_Loss\n"
        "AAA,Core_Dragon,AAA Inc,100,$95\n",
        encoding="utf-8",
    )

    ensure_calls = []
    ns["ensure_trade_history_columns"] = lambda: ensure_calls.append(True)

    result = fn()

    assert result["failed_files"] == [path.name]
    assert ensure_calls == []
    assert path.exists() and not (tmp_path / (path.name + ".processed")).exists()
    assert _trade_rows() == []


def test_header_only_empty_file_is_processed_without_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    path = tmp_path / "us_stocks_pending_20261020.csv"
    path.write_text("Date,Ticker,Tag\n", encoding="utf-8")

    result = fn()
    assert result["failed_files"] == [] and result["incomplete_files"] == []
    assert not path.exists() and (tmp_path / (path.name + ".processed")).exists()
    assert _trade_rows() == []


def test_market_window_covers_pending_target_date(tmp_path, monkeypatch):
    """行情请求必须显式给出覆盖 target_date 的窗口，不能只依赖 period="10d"。

    pending 文件缺行情时会被保留重试；固定 10 天窗口随日期推移会把 target_date
    挤出窗口，届时该文件永远补不上 OHLC，review 每晚 exit 1（2026-10-22 → 10-24 事故）。
    """
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    _write_pending(tmp_path, _rows("AAA"))
    ns["OHLC"][("AAA", TARGET_DATE)] = {"open": "100", "close": "105"}

    assert fn()["incomplete_files"] == []

    call = ns["DOWNLOAD_CALLS"][-1]
    assert call["tickers"] == ["AAA"]
    assert call["start"] is not None and call["end"] is not None
    assert call["start"] <= TARGET_DATE < call["end"]


def test_stale_pending_file_gets_window_around_its_own_date(tmp_path, monkeypatch):
    """滞留多日的 pending 文件：窗口围绕文件自己的日期，而不是"今天往前 10 天"。"""
    monkeypatch.chdir(tmp_path)
    fn, ns = _load_supplement(tmp_path)
    stale_date = "2026-09-01"
    path = _write_pending(tmp_path, [{
        "Date": stale_date, "Ticker": "AAA", "Tag": "Core_Dragon",
        "Name": "AAA Inc", "Scan_Ref_Price": "100", "Stop_Loss": "$95",
    }], name="us_stocks_pending_20260901.csv")
    ns["OHLC"][("AAA", stale_date)] = {"open": "100", "close": "105"}

    assert fn()["incomplete_files"] == []

    call = ns["DOWNLOAD_CALLS"][-1]
    assert call["start"] <= stale_date < call["end"]
    assert not path.exists() and (tmp_path / (path.name + ".processed")).exists()

