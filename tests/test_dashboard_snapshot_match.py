#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G2b：快照匹配回退 + scan_date 跟随（行为级，直调 _attach_snapshot_ai）。"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import dashboard_export as de

_attach = de._attach_snapshot_ai


def _snap(sid, upd, text="TEXT"):
    return {"snapshot_id": sid, "update_date": upd, "texts": {"ai_industry_logic": text}}


def _call(ticker, rec_date, tag, snapshots):
    row = {"Date": rec_date}
    _attach(row, ticker, rec_date, tag, snapshots)
    return row


def test_exact_triple_match_wins():
    snaps = {("ADSK", "2026-10-14", "Core_Dragon"): _snap("S14", "2026-10-14")}
    row = _call("ADSK", "2026-10-14", "Core_Dragon", snaps)
    assert row["Snapshot_Used_Date"] == "2026-10-14"
    assert row["Snapshot_ID"] == "S14"


def test_holding_falls_back_to_latest_when_no_exact_match():
    """持仓：精确 (ADSK,10-07) 不存在 -> 用 (ADSK,10-14)（确有更新）。"""
    snaps = {("ADSK", "2026-10-14", "Core_Dragon"): _snap("S14", "2026-10-14")}
    row = _call("ADSK", "2026-10-07", "Core_Dragon", snaps)
    assert row["Snapshot_Used_Date"] == "2026-10-14"
    assert row["Snapshot_ID"] == "S14"


def test_no_fallback_when_no_newer_snapshot():
    snaps = {("ADSK", "2026-10-07", "Core_Dragon"): _snap("S07", "2026-10-07")}
    row = _call("ADSK", "2026-10-07", "Core_Dragon", snaps)
    assert row["Snapshot_Used_Date"] == "2026-10-07"
    assert row["Snapshot_ID"] == "S07"


def test_no_fallback_when_latest_is_older():
    """只有更早的快照 -> 绝不回退（保护历史事件）。"""
    snaps = {("ADSK", "2026-10-05", "Core_Dragon"): _snap("S05", "2026-10-05")}
    row = _call("ADSK", "2026-10-07", "Core_Dragon", snaps)
    assert "Snapshot_Used_Date" not in row
    assert row["Snapshot_ID"] == ""
    assert "ai_industry_logic" not in row


def test_new_recommendation_unaffected():
    snaps = {("XYZ", "2026-10-14", "Candidate"): _snap("SX", "2026-10-14")}
    row = _call("XYZ", "2026-10-14", "Candidate", snaps)
    assert row["Snapshot_Used_Date"] == "2026-10-14" and row["Snapshot_ID"] == "SX"


def test_no_snapshot_at_all_keeps_row_unchanged():
    row = {"Date": "2026-10-07", "ai_industry_logic": "ORIGINAL"}
    _attach(row, "ADSK", "2026-10-07", "Core_Dragon", {})
    assert row["ai_industry_logic"] == "ORIGINAL"
    assert "Snapshot_Used_Date" not in row
    assert row["Snapshot_ID"] == ""


def test_tag_mismatch_does_not_fall_back():
    """Ticker 相同但 Tag 不同 -> 不是同一事件，禁止回退。"""
    snaps = {("ADSK", "2026-10-14", "Candidate"): _snap("S14", "2026-10-14")}
    row = _call("ADSK", "2026-10-07", "Core_Dragon", snaps)
    assert "Snapshot_Used_Date" not in row


def test_max_rec_date_picks_correctly():
    snaps = {("ADSK", "2026-10-07", "Core_Dragon"): _snap("A", "2026-10-07"),
             ("ADSK", "2026-10-14", "Core_Dragon"): _snap("B", "2026-10-14"),
             ("ADSK", "2026-10-06", "Core_Dragon"): _snap("C", "2026-10-06")}
    row = _call("ADSK", "2026-10-05", "Core_Dragon", snaps)
    assert row["Snapshot_ID"] == "B" and row["Snapshot_Used_Date"] == "2026-10-14"


def test_scan_date_follows_snapshot_source_line():
    """Step 3 契约（源码级）：scan_date 优先取 Snapshot_Used_Date。"""
    src = (REPO / "dashboard_export.py").read_text(encoding="utf-8")
    assert 'clean_text(row.get("Snapshot_Used_Date"))' in src
    assert '"scan_date"' in src
