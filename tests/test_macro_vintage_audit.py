# -*- coding: utf-8 -*-
"""Tests for macro vintage availability status."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from macro_vintage_audit import SERIES, audit_environment, summarize  # noqa: E402


def test_environment_does_not_print_key():
    out = audit_environment()
    assert "fred_api_key_present" in out
    assert "key_value_printed" in out and out["key_value_printed"] is False


def test_no_records_is_zero_not_fabricated():
    assert summarize([])["records"] == 0
    assert summarize([])["first_release_available"] == 0


def test_series_catalog_present():
    assert "CPIAUCSL" in SERIES
    assert "PAYEMS" in SERIES
