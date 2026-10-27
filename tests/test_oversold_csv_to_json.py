# -*- coding: utf-8 -*-
"""CSV → oversold_candidates.json 的格式转换测试（不含任何筛选/阈值逻辑）。

覆盖：
  · 英文/中文表头映射；
  · $ , % 与 unicode 负号清洗；
  · 缺 ticker 的行被跳过（不补造）；
  · 全部无有效行 → 默认报错退出，--allow-empty 才写空数组；
  · 输出可被 dashboard_export._read_oversold 正常读取（契约对齐）。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(_REPO_ROOT))

import dashboard_export as de  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "oversold_csv", _REPO_ROOT / "scripts" / "oversold_csv_to_json.py")
csvmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csvmod)


def _write_csv(tmp_path: Path, text: str, name="in.csv") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_english_headers_and_cleaning(tmp_path):
    csv_text = (
        "ticker,name,score,tag,rsi,bias_pct,drawdown_pct,ref_price,stop_loss,confirm,invalid,observe_until,reason\n"
        'xyz,XYZ Inc,82.5,超跌反弹,22.4,-14.2,-28.5,"$95.20","$88.50",RSI>30,破前低,2026-11-05,一次性事件\n'
    )
    src = _write_csv(tmp_path, csv_text)
    out = tmp_path / "dashboard" / "data" / "oversold_candidates.json"
    rc = csvmod.main([str(src), "--out", str(out), "--asof", "2026-10-24", "--source", "GPT 研究"])
    assert rc == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    c = payload["candidates"][0]
    assert c["ticker"] == "XYZ"          # 大写
    assert c["score"] == 82.5
    assert c["rsi"] == 22.4
    assert c["bias_pct"] == -14.2
    assert c["drawdown_pct"] == -28.5
    assert c["ref_price"] == 95.2
    assert c["stop_loss"] == 88.5
    assert payload["asof"] == "2026-10-24"
    assert payload["source"] == "GPT 研究"
    assert payload["schema"] == 1


def test_chinese_headers(tmp_path):
    csv_text = (
        "代码,名称,超跌分,标签,RSI,偏离,回撤,参考价,止损,确认条件,失效条件,观察至,理由\n"
        "abc,ABC 公司,74,错杀观察,27.8,-9.6%,-21.3%,$41.30,$38.90,日线止跌,跌破 $38.90,2026-11-02,beta 回调\n"
    )
    src = _write_csv(tmp_path, csv_text)
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out)]) == 0
    c = json.loads(out.read_text(encoding="utf-8"))["candidates"][0]
    assert c["ticker"] == "ABC"
    assert c["name"] == "ABC 公司"
    assert c["drawdown_pct"] == -21.3
    assert c["confirm"] == "日线止跌"
    assert c["observe_until"] == "2026-11-02"


def test_missing_ticker_rows_are_skipped(tmp_path):
    csv_text = (
        "ticker,score,reason\n"
        "a,1,ok\n"
        ",2,no ticker\n"
        "b,3,ok2\n"
    )
    src = _write_csv(tmp_path, csv_text)
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [c["ticker"] for c in payload["candidates"]] == ["A", "B"]


def test_all_rows_invalid_fails_without_allow_empty(tmp_path):
    src = _write_csv(tmp_path, "ticker,score\n,1\n,2\n")
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out)]) == 1
    assert not out.exists()


def test_allow_empty_writes_empty_candidates(tmp_path):
    src = _write_csv(tmp_path, "ticker,score\n,1\n")
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out), "--allow-empty"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["candidates"] == []


def test_dry_run_does_not_write(tmp_path, capsys):
    src = _write_csv(tmp_path, "ticker,score\nx,1\n")
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert '"ticker": "X"' in capsys.readouterr().out


def test_output_matches_dashboard_contract(tmp_path):
    src = _write_csv(tmp_path, "ticker,score,rsi\nxyz,82.5,22.4\n")
    out = tmp_path / "dashboard" / "data" / "oversold_candidates.json"
    assert csvmod.main([str(src), "--out", str(out)]) == 0
    parsed = de._read_oversold(tmp_path)
    assert parsed["count"] == 1
    assert parsed["candidates"][0]["ticker"] == "XYZ"
    assert parsed["candidates"][0]["score"] == 82.5
    assert parsed["candidates"][0]["rsi"] == 22.4


def test_unicode_minus_and_bad_numbers(tmp_path):
    csv_text = "ticker,bias_pct,score\nz,\u221214.2,n/a\n"
    src = _write_csv(tmp_path, csv_text)
    out = tmp_path / "o.json"
    assert csvmod.main([str(src), "--out", str(out)]) == 0
    c = json.loads(out.read_text(encoding="utf-8"))["candidates"][0]
    assert c["bias_pct"] == -14.2
    assert c["score"] is None          # 无法解析 → None，绝不补 0
