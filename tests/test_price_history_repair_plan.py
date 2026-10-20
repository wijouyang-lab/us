from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from plan_price_history_repair import (  # noqa: E402
    build_repair_plan,
    write_plan_csv,
)


COLUMNS = [
    "Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"
]


def write_prices(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def test_plan_matches_v2_close_but_flags_volume_mismatch(tmp_path):
    path = tmp_path / "prices.csv"
    write_prices(
        path,
        [
            ["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-11", "AAPL", "10", "12", "9", "11", "250", "phase2b.v1"],
        ],
    )
    before = path.read_bytes()

    plan, summary = build_repair_plan(path)

    assert len(plan) == 1
    assert plan[0]["Proposed_Date_Offset"] == "2026-10-12"
    assert plan[0]["Reference_V2_Exists"] == "true"
    assert plan[0]["Close_Comparison"] == "MATCH"
    assert plan[0]["Classification"] == "CLOSE_MATCH_OTHER_FIELDS_DIFFER"
    assert plan[0]["Mismatched_Fields"] == "Volume"
    assert plan[0]["Recommended_Next_Action"] == "REVIEW_FIELD_DIFFERENCES_AND_PREFER_VERIFIED_V2"
    assert summary["legacy_schema_rows_planned"] == 1
    assert summary["legacy_rows_with_v2_reference_at_proposed_date"] == 1
    assert summary["close_equal"] == 1
    assert summary["close_mismatches"] == 0
    assert summary["field_mismatches"]["Volume"] == 1
    assert summary["automatic_repair_performed"] is False
    assert path.read_bytes() == before


def test_plan_classifies_rows_without_v2_reference(tmp_path):
    path = tmp_path / "prices.csv"
    write_prices(
        path,
        [
            ["2026-10-08", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-09", "MSFT", "", "", "", "20", "", "phase2b.v1"],
            ["2026-10-17", "NVDA", "", "", "", "30", "", "phase2b.v1"],
        ],
    )

    plan, summary = build_repair_plan(path)
    by_ticker = {row["Ticker"]: row for row in plan}

    assert by_ticker["MSFT"]["Proposed_Date_Offset"] == "2026-10-10"
    assert by_ticker["MSFT"]["Classification"] == "NO_V2_REFERENCE_AFTER_V2_RANGE"
    assert by_ticker["NVDA"]["Proposed_Date_Offset"] == "2026-10-18"
    assert by_ticker["NVDA"]["Classification"] == "NO_V2_REFERENCE_AFTER_V2_RANGE"
    assert summary["proposed_target_weekend_rows"] == 1
    assert summary["close_mismatches"] == 0


def test_plan_fails_closed_on_close_mismatch(tmp_path):
    path = tmp_path / "prices.csv"
    write_prices(
        path,
        [
            ["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-11", "AAPL", "10", "12", "9", "10.5", "300", "phase2b.v1"],
        ],
    )

    plan, summary = build_repair_plan(path)

    assert plan[0]["Classification"] == "CLOSE_MISMATCH_NEEDS_SOURCE_REVIEW"
    assert plan[0]["Recommended_Next_Action"] == "STOP_AND_REBUILD_FROM_AUTHORITATIVE_DAILY_BAR"
    assert summary["close_mismatches"] == 1


def test_plan_marks_duplicate_v2_reference_as_ambiguous(tmp_path):
    path = tmp_path / "prices.csv"
    write_prices(
        path,
        [
            ["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-11", "AAPL", "10", "12", "9", "11", "300", "phase2b.v1"],
        ],
    )

    plan, summary = build_repair_plan(path)

    assert plan[0]["Classification"] == "DUPLICATE_V2_REFERENCE"
    assert summary["invalid_v2_reference_rows"] == 0


def test_plan_csv_is_separate_and_input_remains_unchanged(tmp_path):
    path = tmp_path / "prices.csv"
    output = tmp_path / "plan.csv"
    write_prices(
        path,
        [
            ["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"],
            ["2026-10-11", "AAPL", "10", "12", "9", "11", "300", "phase2b.v1"],
        ],
    )
    before = path.read_bytes()
    plan, _ = build_repair_plan(path)

    saved = write_plan_csv(plan, output, path)

    assert saved == output
    assert path.read_bytes() == before
    with output.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 1
    assert written[0]["Proposed_Date_Offset"] == "2026-10-12"
    assert output != path


def test_plan_refuses_to_overwrite_input_or_existing_plan(tmp_path):
    path = tmp_path / "prices.csv"
    output = tmp_path / "plan.csv"
    write_prices(
        path,
        [["2026-10-12", "AAPL", "10", "12", "9", "11", "300", "phase2b.v2"]],
    )
    plan, _ = build_repair_plan(path)

    with pytest.raises(ValueError, match="over the price history input"):
        write_plan_csv(plan, path, path)
    output.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_plan_csv(plan, output, path)
    assert output.read_text(encoding="utf-8") == "keep me"
