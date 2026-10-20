# -*- coding: utf-8 -*-
"""Fail-closed regression tests for the $50,000 paper portfolio's intraday stop path."""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import portfolio_50000 as pf


ET = ZoneInfo("America/New_York")
TODAY = "2026-10-20"
NOW_OPEN = datetime(2026, 10, 20, 10, 30, tzinfo=ET)


def _write_rows(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _position(stop_loss="$95.00") -> dict:
    row = {column: "" for column in pf.POSITION_COLUMNS}
    row.update({
        "Portfolio_ID": pf.PORTFOLIO_ID,
        "Unit_ID": "U001",
        "Ticker": "AAA",
        "Shares": "10",
        "Entry_Price": "100.00",
        "Entry_Date": "2026-10-16",
        "Cost_Basis": "1000.00",
        "Current_Price": "100.00",
        "Market_Value": "1000.00",
        "Unrealized_PnL": "0.00",
        "Unrealized_PnL_Pct": "0.00",
        "Weight_Pct": "2.00",
        "Status": "OPEN",
        "Stop_Loss": stop_loss,
        # Intentionally no dependence on a successful Recommendation_ID lookup/sync.
        "Recommendation_ID": "",
        "Last_Update": "2026-10-19",
        "Cooldown_Until": "",
    })
    return row


def _setup(tmp_path: Path, stop_loss="$95.00") -> None:
    _write_rows(tmp_path / pf.POSITIONS_FILE, pf.POSITION_COLUMNS, [_position(stop_loss)])
    _write_rows(tmp_path / pf.TRANSACTIONS_FILE, pf.TRANSACTION_COLUMNS, [])


def test_numeric_parser_accepts_currency_formatted_prices():
    assert pf.dec("$95.00") == Decimal("95.00")
    assert pf.dec("$1,234.56") == Decimal("1234.56")
    assert pf.dec("N/A") is None
    assert pf.dec("") is None


def test_intraday_stop_triggers_on_valid_dollar_formatted_stop(tmp_path, monkeypatch):
    _setup(tmp_path, "$95.00")
    monkeypatch.setattr(
        pf, "fetch_last_closes",
        lambda tickers: {"AAA": {"current": Decimal("94.00"), "extended": None, "extended_time": ""}},
    )

    result = pf._run_intraday_stop(tmp_path, TODAY, offline=False, now_et=NOW_OPEN)

    assert result["triggered"] == 1
    positions = _read_rows(tmp_path / pf.POSITIONS_FILE)
    assert positions[0]["Status"] == "CLOSED"
    assert positions[0]["Shares"] == "0"
    txns = _read_rows(tmp_path / pf.TRANSACTIONS_FILE)
    assert len(txns) == 1
    assert txns[0]["Action"] == "SELL"
    assert txns[0]["Reason"] == "Intraday Stop Loss"
    assert txns[0]["Price"] == "94.00"


def test_intraday_stop_fails_closed_when_quote_missing(tmp_path, monkeypatch):
    _setup(tmp_path, "$95.00")
    before = (tmp_path / pf.POSITIONS_FILE).read_text(encoding="utf-8")
    monkeypatch.setattr(pf, "fetch_last_closes", lambda tickers: {})

    result = pf._run_intraday_stop(tmp_path, TODAY, offline=False, now_et=NOW_OPEN)

    assert result["triggered"] == 0
    assert (tmp_path / pf.POSITIONS_FILE).read_text(encoding="utf-8") == before
    assert _read_rows(tmp_path / pf.TRANSACTIONS_FILE) == []


def test_intraday_stop_does_not_run_outside_regular_session(tmp_path, monkeypatch):
    _setup(tmp_path, "$95.00")
    before = (tmp_path / pf.POSITIONS_FILE).read_text(encoding="utf-8")
    called = []
    monkeypatch.setattr(pf, "fetch_last_closes", lambda tickers: called.append(True) or {})

    after_hours = datetime(2026, 10, 20, 17, 0, tzinfo=ET)
    result = pf._run_intraday_stop(tmp_path, TODAY, offline=False, now_et=after_hours)

    assert result["triggered"] == 0
    assert called == []
    assert (tmp_path / pf.POSITIONS_FILE).read_text(encoding="utf-8") == before
    assert _read_rows(tmp_path / pf.TRANSACTIONS_FILE) == []

