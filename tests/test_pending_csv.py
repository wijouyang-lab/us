# -*- coding: utf-8 -*-
"""Tests for strict pending CSV parsing (Task B)."""

import pytest

from pending_csv import PendingCsvError, read_pending_csv


def _write(tmp_path, text, name="us_stocks_pending_20261020.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def test_normal_csv_with_empty_fields_is_valid(tmp_path):
    path = _write(
        tmp_path,
        "Date,Ticker,Tag,Name\n2026-10-20,AAA,Core_Dragon,\n",
    )
    header, rows = read_pending_csv(path)
    assert header == ["Date", "Ticker", "Tag", "Name"]
    assert rows == [{"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Core_Dragon", "Name": ""}]


def test_header_only_is_valid_empty_file(tmp_path):
    path = _write(tmp_path, "Date,Ticker,Tag\n")
    header, rows = read_pending_csv(path)
    assert header == ["Date", "Ticker", "Tag"]
    assert rows == []


def test_zero_byte_file_is_error(tmp_path):
    path = _write(tmp_path, "")
    with pytest.raises(PendingCsvError, match="empty file"):
        read_pending_csv(path)


def test_field_count_mismatch_is_error(tmp_path):
    path = _write(tmp_path, "Date,Ticker,Tag\n2026-10-20,AAA\n")
    with pytest.raises(PendingCsvError, match="line 2: expected 3 fields, got 2"):
        read_pending_csv(path)


def test_extra_field_is_error(tmp_path):
    path = _write(tmp_path, "Date,Ticker,Tag\n2026-10-20,AAA,Core,EXTRA\n")
    with pytest.raises(PendingCsvError, match="expected 3 fields, got 4"):
        read_pending_csv(path)


def test_unclosed_quote_is_error(tmp_path):
    path = _write(tmp_path, 'Date,Ticker,Tag\n2026-10-20,"AAA,Core\n')
    with pytest.raises(PendingCsvError, match="malformed CSV|unexpected end"):
        read_pending_csv(path)


def test_duplicate_header_is_error(tmp_path):
    path = _write(tmp_path, "Date,Ticker,Ticker\n2026-10-20,AAA,Core\n")
    with pytest.raises(PendingCsvError, match="duplicate header"):
        read_pending_csv(path)


def test_missing_file_is_error(tmp_path):
    with pytest.raises(PendingCsvError, match="does not exist"):
        read_pending_csv(tmp_path / "missing.csv")
