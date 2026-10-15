#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trade_history.csv 的 Status 一致性巡检（防回归）。

规则：Status == "Stop_Loss_Hit" 的行，若 exit 与 entry 均可解析且 > 0，
      则必须 exit <= entry（真止损不应盈利）。

历史豁免（同 ticker 多笔共享同一 Exit_Price，疑似同一事件多条记录，
          数据口径待人工审查 → 暂不纳入本次修正，测试豁免）：
  - 2026-06-19 MSTR
  - 2026-06-24 MSTR
  - 2026-06-26 AMD
  - 2026-08-14 AMD
  - 2026-06-08 MU
  - 2026-06-09 MU

豁免清单的清理条件：当上述记录的 Exit_Price 被人工核对修正后，
应同步从本豁免清单移除。
"""
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRADE_HISTORY = REPO / "trade_history.csv"

# 豁免清单：(Date[:10], Ticker)
EXEMPTIONS = {
    ("2026-06-19", "MSTR"),
    ("2026-06-24", "MSTR"),
    ("2026-06-26", "AMD"),
    ("2026-08-14", "AMD"),
    ("2026-06-08", "MU"),
    ("2026-06-09", "MU"),
}


def _parse_float(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (ValueError, TypeError):
        return None


def test_stop_loss_hit_rows_must_not_be_profitable():
    """Status=Stop_Loss_Hit 的行不应 exit > entry（豁免清单除外）。"""
    assert TRADE_HISTORY.exists(), f"未找到 {TRADE_HISTORY}"

    violations = []
    with open(TRADE_HISTORY, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("Status") or "").strip() != "Stop_Loss_Hit":
                continue
            entry = _parse_float(row.get("Price"))
            exitp = _parse_float(row.get("Exit_Price"))
            if entry is None or exitp is None:
                continue
            if exitp <= entry:
                continue
            key = ((row.get("Date") or "")[:10], (row.get("Ticker") or "").strip())
            if key in EXEMPTIONS:
                continue
            violations.append((key, entry, exitp))

    assert not violations, (
        f"发现 {len(violations)} 笔 Stop_Loss_Hit 但 exit > entry（不在豁免清单）：\n"
        + "\n".join(f"  {k[0]} {k[1]}: entry={e} exit={x}" for k, e, x in violations)
    )
