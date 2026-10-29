# -*- coding: utf-8 -*-
"""Fixture checks for SEC timestamp audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_sec_sample_and_sgml_limit():
    d = json.loads((ROOT / "sec_timestamp_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["http"] == 200
    assert d["parsed"] == 10
    assert d["missing"] == 0
    assert d["date_mismatch"] == 0
    assert d["sgml"]["http"] == 403
    assert d["sgml"]["acceptance_header_present"] is False


def test_sec_acceptance_is_not_first_seen():
    d = json.loads((ROOT / "sec_timestamp_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert "first-public-availability" in d["note"]
    assert all("acceptance_utc" in x for x in d["sample"])
