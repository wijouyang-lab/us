# -*- coding: utf-8 -*-
"""Regression tests for same-day pending merge (P0-1)."""

import csv
import os
import threading
from pathlib import Path

import pytest

import pending_store


FIELDS = ["Date", "Ticker", "Tag", "Name", "Stop_Loss", "AI_Score", "Premarket_Price"]


def _row(ticker="AAA", tag="Core_Dragon", date="2026-10-20", **extra):
    base = {
        "Date": date,
        "Ticker": ticker,
        "Tag": tag,
        "Name": ticker + " Inc",
        "Stop_Loss": "$95",
        "AI_Score": "70",
        "Premarket_Price": "101",
    }
    base.update(extra)
    return base


def _read(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_two_scans_keep_both_recommendations(tmp_path):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    pending_store.merge_pending_file(path, [_row("AAA")], FIELDS)
    pending_store.merge_pending_file(path, [_row("BBB")], FIELDS)
    rows = _read(path)
    assert [r["Ticker"] for r in rows] == ["AAA", "BBB"]
    assert set(rows[0]) == set(FIELDS)


def test_same_event_twice_is_not_duplicated_and_nonempty_fields_win(tmp_path):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    pending_store.merge_pending_file(path, [_row("AAA")], FIELDS)
    pending_store.merge_pending_file(
        path,
        [_row("AAA", AI_Score="88", Stop_Loss="", Name="")],
        FIELDS,
    )
    rows = _read(path)
    assert len(rows) == 1
    assert rows[0]["AI_Score"] == "88"
    # Empty values from the second scan must not erase valid earlier fields.
    assert rows[0]["Stop_Loss"] == "$95"
    assert rows[0]["Name"] == "AAA Inc"


def test_processed_event_is_not_requeued(tmp_path):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    processed = Path(str(path) + ".processed")
    with processed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(_row("AAA"))

    stats = pending_store.merge_pending_file(
        path, [_row("AAA"), _row("BBB")], FIELDS, processed_path=processed
    )
    rows = _read(path)
    assert [r["Ticker"] for r in rows] == ["BBB"]
    assert stats["processed_skipped"] == 1
    assert ("2026-10-20", "AAA", "Core_Dragon") in stats["skipped_event_keys"]

    # Re-running the same consumed event must not resurrect it.
    pending_store.merge_pending_file(path, [_row("AAA")], FIELDS, processed_path=processed)
    assert [r["Ticker"] for r in _read(path)] == ["BBB"]


def test_old_header_is_preserved_and_new_columns_are_appended(tmp_path):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    old_fields = ["Date", "Ticker", "Tag", "Legacy_Field"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=old_fields)
        writer.writeheader()
        writer.writerow({
            "Date": "2026-10-20", "Ticker": "OLD", "Tag": "Observation",
            "Legacy_Field": "keep-me",
        })

    pending_store.merge_pending_file(path, [_row("NEW")], FIELDS)
    rows = _read(path)
    with path.open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    assert header[:4] == old_fields
    assert set(FIELDS).issubset(set(header))
    assert rows[0]["Legacy_Field"] == "keep-me"
    assert rows[1]["Ticker"] == "NEW"


def test_write_failure_leaves_original_intact(tmp_path, monkeypatch):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    pending_store.merge_pending_file(path, [_row("AAA")], FIELDS)
    before = path.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(pending_store.os, "replace", boom)
    with pytest.raises(OSError):
        pending_store.merge_pending_file(path, [_row("BBB")], FIELDS)

    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_merges_keep_both_events(tmp_path):
    path = tmp_path / "us_stocks_pending_20261020.csv"
    start = threading.Barrier(2)
    errors = []

    def worker(ticker):
        try:
            start.wait(timeout=5)
            pending_store.merge_pending_file(
                path, [_row(ticker)], FIELDS, lock_timeout=10
            )
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in ("AAA", "BBB")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors
    assert sorted(r["Ticker"] for r in _read(path)) == ["AAA", "BBB"]
    assert not list(tmp_path.glob("*.tmp"))
