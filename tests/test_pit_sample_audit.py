# -*- coding: utf-8 -*-
"""Fixture checks for PIT sample audit."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research"


def test_pit_audit_counts_and_rejections():
    d = json.loads((ROOT / "pit_sample_audit_2026-10-29.json").read_text(encoding="utf-8"))
    assert d["unique_events"] == 3
    assert d["pit_admitted"] == 0
    assert d["late_observations"] == 2
    assert d["historical_backfills"] == 1
    assert d["simulated_records"] == 0
    assert d["real_first_seen_records"] == 1
    assert "20100127" in d["events"]
    assert "late_observation" in d["events"]["20250319"]


def test_unmatched_glob_is_an_error(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
    import pit_sample_audit as a
    try:
        a.main(["--store", str(tmp_path / "missing*.jsonl"), "--output", str(tmp_path / "o.json")])
    except SystemExit as exc:
        assert "matched no files" in str(exc)
    else:
        raise AssertionError("missing glob did not fail")


def test_empty_file_is_not_silent_success(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
    import pit_sample_audit as a
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    out = tmp_path / "o.json"
    a.main(["--store", str(p), "--output", str(out)])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["status"] == "no_valid_records"
    assert str(p) in d["empty_files"]
