from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.research.audit_date_integrity import (
    audit_files,
    audit_price_history,
    audit_snapshot,
    main,
)


def write_csv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def test_snapshot_audit_detects_weekend_session_dates_and_duplicate_keys(tmp_path):
    path = tmp_path / "snapshot.csv"
    write_csv(
        path,
        ["Scan_Date", "Technical_Date", "Ticker", "schema_version"],
        [
            ["2026-10-19", "2026-10-18", "AAPL", "phase1.v1"],
            ["2026-10-19", "2026-10-18", "aapl", "phase1.v1"],
            ["2026-10-20", "2026-10-16", "MSFT", "phase1.v1"],
        ],
    )

    result = audit_snapshot(path)

    assert result["rows"] == 3
    assert result["technical_weekend_rows"] == 2
    assert result["technical_weekday_counts"] == {
        "Fri": 1,
        "Sun": 2,
    }
    assert result["duplicate_scan_date_ticker_keys"] == 1
    assert result["scan_minus_technical_calendar_days"] == {
        "+1": 2,
        "+4": 1,
    }


def test_price_history_audit_detects_mixed_schema_and_weekend_labels(tmp_path):
    path = tmp_path / "price_history.csv"
    write_csv(
        path,
        ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"],
        [
            ["2026-10-12", "AAPL", "100", "102", "99", "101", "1000", "phase2b.v2"],
            ["2026-10-11", "aapl", "99", "101", "98", "100", "900", "phase2b.v1"],
        ],
    )

    result = audit_price_history(path)

    assert result["rows"] == 2
    assert result["unique_tickers"] == 1
    assert result["schema_versions"] == {"phase2b.v1": 1, "phase2b.v2": 1}
    assert result["legacy_or_unexpected_schema_rows"] == 1
    assert result["weekend_date_rows"] == 1
    assert result["weekend_rows_by_schema"] == {"phase2b.v1": 1}
    # The physical keys differ, even though the old row may be a misdated version
    # of the corrected session; the auditor must not silently rewrite it.
    assert result["duplicate_date_ticker_keys"] == 0


def test_clean_files_pass_strict_audit(tmp_path):
    snapshot = tmp_path / "snapshot.csv"
    prices = tmp_path / "prices.csv"
    write_csv(
        snapshot,
        ["Scan_Date", "Technical_Date", "Ticker", "schema_version"],
        [["2026-10-19", "2026-10-16", "AAPL", "phase1.v1"]],
    )
    write_csv(
        prices,
        ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"],
        [["2026-10-16", "AAPL", "100", "102", "99", "101", "1000", "phase2b.v2"]],
    )

    report = audit_files(snapshot, prices)

    assert report["read_only"] is True
    assert report["issues"] == []
    assert report["strict_pass"] is True


def test_audit_never_modifies_input_files(tmp_path):
    snapshot = tmp_path / "snapshot.csv"
    prices = tmp_path / "prices.csv"
    write_csv(
        snapshot,
        ["Scan_Date", "Technical_Date", "Ticker", "schema_version"],
        [["2026-10-19", "2026-10-18", "AAPL", "phase1.v1"]],
    )
    write_csv(
        prices,
        ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"],
        [["2026-10-11", "AAPL", "100", "102", "99", "101", "1000", "phase2b.v1"]],
    )
    before = {p: p.read_bytes() for p in (snapshot, prices)}

    audit_files(snapshot, prices)

    assert {p: p.read_bytes() for p in (snapshot, prices)} == before


def test_strict_cli_returns_nonzero_and_prints_json_for_issues(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.csv"
    prices = tmp_path / "prices.csv"
    write_csv(
        snapshot,
        ["Scan_Date", "Technical_Date", "Ticker", "schema_version"],
        [["2026-10-19", "2026-10-18", "AAPL", "phase1.v1"]],
    )
    write_csv(
        prices,
        ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"],
        [["2026-10-11", "AAPL", "100", "102", "99", "101", "1000", "phase2b.v1"]],
    )

    exit_code = main([
        "--snapshot", str(snapshot),
        "--price-history", str(prices),
        "--strict",
    ])
    out = capsys.readouterr().out
    parsed = json.loads(out)

    assert exit_code == 1
    assert parsed["strict_pass"] is False
    assert parsed["issues"]
