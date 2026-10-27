# -*- coding: utf-8 -*-
"""规则版超跌候选生成器：过滤、评分、契约字段、fail-closed。"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "oversold_screen", _REPO_ROOT / "scripts" / "oversold_screen.py")
os_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(os_mod)

import dashboard_export as de  # noqa: E402

HEADER = ("Scan_Date,Technical_Date,Ticker,Name,Sector,Price,RSI_14,Bias_Pct,"
          "ZScore_20D,ATR_Pct,Volume_Ratio_20D,Momentum_20D_Pct,MA20\n")


def _row(ticker="AAA", rsi=25, bias=-12, z=-2.2, px=50, atr=4, vr=1.0,
         mom=-10, ma20=56, scan="2026-10-26"):
    return (f"{scan},2026-10-25,{ticker},Name {ticker},Tech,{px},{rsi},{bias},"
            f"{z},{atr},{vr},{mom},{ma20}\n")


def _write(tmp_path: Path, body: str):
    p = tmp_path / "quant_factor_snapshot.csv"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


def test_accepts_matching_row(tmp_path):
    p = _write(tmp_path, _row())
    asof, rows = os_mod.load_latest_rows(p)
    assert asof == "2026-10-26"
    out = os_mod.screen(rows, asof)
    assert len(out) == 1
    c = out[0]
    assert c["ticker"] == "AAA"
    assert 0 <= c["score"] <= 100
    assert c["tag"] == "超跌反弹"
    assert c["drawdown_pct"] == -10.0
    assert c["stop_loss"] < c["ref_price"]
    assert c["observe_until"] == "2026-11-05"
    assert "未回测" in c["reason"]


def test_filters_reject_bad_rows(tmp_path):
    body = (
        _row("HIGHRSI", rsi=45) +
        _row("SHALLOW", bias=-3) +
        _row("HIGHZ", z=0.2) +
        _row("PENNY", px=2) +
        _row("QUIET", atr=0.8) +
        _row("WILD", atr=12) +
        _row("ILLIQ", vr=0.1)
    )
    p = _write(tmp_path, body)
    asof, rows = os_mod.load_latest_rows(p)
    assert os_mod.screen(rows, asof) == []


def test_sorted_by_score_and_capped(tmp_path):
    body = "".join(_row(f"T{i}", rsi=30 - i, bias=-9 - i) for i in range(15))
    p = _write(tmp_path, body)
    asof, rows = os_mod.load_latest_rows(p)
    out = os_mod.screen(rows, asof, max_candidates=10)
    assert len(out) == 10
    scores = [c["score"] for c in out]
    assert scores == sorted(scores, reverse=True)


def test_uses_latest_scan_date_only(tmp_path):
    body = _row("OLD", scan="2026-10-20") + _row("NEW", scan="2026-10-26")
    p = _write(tmp_path, body)
    asof, rows = os_mod.load_latest_rows(p)
    assert asof == "2026-10-26"
    assert [r["Ticker"] for r in rows] == ["NEW"]


def test_missing_snapshot_keeps_old_file(tmp_path):
    out = tmp_path / "out" / "oversold_candidates.json"
    out.parent.mkdir()
    out.write_text('{"schema": 1, "candidates": [{"ticker": "KEEP"}]}', encoding="utf-8")
    rc = os_mod.main(["--snapshot", str(tmp_path / "nope.csv"), "--out", str(out)])
    assert rc == 0
    assert "KEEP" in out.read_text(encoding="utf-8")


def test_output_readable_by_dashboard_export(tmp_path):
    p = _write(tmp_path, _row())
    repo = tmp_path / "repo"
    (repo / "dashboard" / "data").mkdir(parents=True)
    out = repo / "dashboard" / "data" / "oversold_candidates.json"
    rc = os_mod.main(["--snapshot", str(p), "--out", str(out)])
    assert rc == 0
    parsed = de._read_oversold(repo)
    assert parsed is not de._OVERSOLD_MISSING
    assert parsed["count"] == 1
    assert parsed["candidates"][0]["ticker"] == "AAA"
