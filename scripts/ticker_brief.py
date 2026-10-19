#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 线 CLI 简报 v0 —— 单只 ticker 的结构化简报（只读）

用法：
    python scripts/ticker_brief.py AAPL
    python scripts/ticker_brief.py AAPL --date 2026-10-16

数据来源（全部只读，不 import 任何生产模块）：
    1. ai_snapshot.csv            → AI 历史（该 ticker 的快照记录）
    2. quant_factor_snapshot.csv  → 因子位置（最新值 + 全体分位数）
    3. trade_history.csv          → 类似历史交易（该 ticker；无则退化为同 Sector）
    4. macro_data.json + dashboard/data/market_indicators.json → 宏观环境

约束：
    · 不写任何文件，只 print
    · 缺数据时输出 N/A，不抛异常
    · 退出码恒为 0（除非 argparse 用法错误）
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

AI_SNAPSHOT = REPO / "ai_snapshot.csv"
QUANT_SNAPSHOT = REPO / "quant_factor_snapshot.csv"
TRADE_HISTORY = REPO / "trade_history.csv"
MACRO_DATA = REPO / "macro_data.json"
MARKET_INDICATORS = REPO / "dashboard" / "data" / "market_indicators.json"
NA = "N/A"

# 简报展示的因子列（与 quant_factor_lab.SNAPSHOT_COLUMNS 同源，但此处独立声明，不 import）
FACTORS = [
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY", "Quant_Score",
    "RSI", "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct",
    "乖离率(%)", "MACD_HIST_LAST", "KDJ_J", "量比",
]


# ---------------------------------------------------------------- 工具函数
def read_csv(path: Path) -> list[dict]:
    """读取 CSV 为 dict 列表；文件缺失/损坏返回空列表（不抛异常）。"""
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def read_json(path: Path) -> dict:
    """读取 JSON；缺失/损坏返回空 dict。"""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def num(value):
    """尽力转 float；失败返回 None。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() == NA:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def fmt(value, digits: int = 2) -> str:
    """数值格式化；None → N/A。"""
    v = num(value)
    return NA if v is None else f"{v:.{digits}f}"


def pct_rank(values: list[float], target: float) -> str:
    """target 在 values 中的百分位（0-100）；样本不足返回 N/A。"""
    if target is None or len(values) < 5:
        return NA
    below = sum(1 for v in values if v < target)
    return f"{below / len(values) * 100:.0f}"


def section(title: str) -> None:
    print()
    print(f"## {title}")
    print()


# ---------------------------------------------------------------- 各数据块
def block_ai(ticker: str) -> None:
    section("1. AI 历史（ai_snapshot.csv）")
    rows = [r for r in read_csv(AI_SNAPSHOT) if (r.get("Ticker") or "").strip().upper() == ticker]
    if not rows:
        print(f"- {NA}（无 AI 快照记录）")
        return
    rows.sort(key=lambda r: (r.get("Rec_Date") or "", r.get("Snapshot_ID") or ""), reverse=True)
    print(f"- 记录数：{len(rows)}")
    print()
    print("| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |")
    print("|---|---|---|---|---|")
    for r in rows[:5]:
        print("| {} | {} | {} | {} | {} |".format(
            r.get("Rec_Date") or NA,
            r.get("Tag") or NA,
            r.get("Snapshot_Type") or NA,
            fmt(r.get("Final_Score")),
            fmt(r.get("AI_Score")),
        ))


def block_quant(ticker: str, as_of: str | None) -> None:
    section("2. 因子位置（quant_factor_snapshot.csv）")
    rows = read_csv(QUANT_SNAPSHOT)
    if not rows:
        print(f"- {NA}（quant_factor_snapshot.csv 缺失或为空）")
        return
    dates = sorted({(r.get("Scan_Date") or "") for r in rows if r.get("Scan_Date")})
    if not dates:
        print(f"- {NA}（无 Scan_Date）")
        return
    target_date = as_of if (as_of and as_of in dates) else dates[-1]
    if as_of and as_of not in dates:
        print(f"- 提示：{as_of} 不在快照日期列表内，改用最新 {target_date}")
    same_day = [r for r in rows if (r.get("Scan_Date") or "") == target_date]
    mine = [r for r in same_day if (r.get("Ticker") or "").strip().upper() == ticker]
    print(f"- 快照日期：{target_date}（该日共 {len(same_day)} 只；全表 {len(dates)} 个日期 / {len(rows)} 行）")
    if not mine:
        print(f"- {NA}（该 ticker 在 {target_date} 无因子快照）")
        return
    r = mine[0]
    print(f"- Sector：{r.get('Sector') or NA}　Price：{fmt(r.get('Price'))}")
    print()
    print("| 因子 | 值 | 当日百分位 |")
    print("|---|---|---|")
    for f in FACTORS:
        if f not in r:
            continue
        val = num(r.get(f))
        if val is None:
            continue
        col = [num(x.get(f)) for x in same_day]
        col = [v for v in col if v is not None]
        print(f"| {f} | {val:.4f} | {pct_rank(col, val)} |")


def block_history(ticker: str) -> None:
    section("3. 类似历史交易（trade_history.csv）")
    rows = read_csv(TRADE_HISTORY)
    if not rows:
        print(f"- {NA}（trade_history.csv 缺失或为空）")
        return
    mine = [r for r in rows if (r.get("Ticker") or "").strip().upper() == ticker]
    scope = f"{ticker}"
    if not mine:
        # 退化：先找该 ticker 的 Sector（来自 quant 快照），再取同 Sector 的历史
        sector = ""
        for r in read_csv(QUANT_SNAPSHOT):
            if (r.get("Ticker") or "").strip().upper() == ticker and r.get("Sector"):
                sector = r["Sector"]
                break
        if sector:
            pool = {((r.get("Ticker") or "").strip().upper()) for r in read_csv(QUANT_SNAPSHOT)
                    if (r.get("Sector") or "") == sector}
            mine = [r for r in rows if (r.get("Ticker") or "").strip().upper() in pool]
            scope = f"同 Sector（{sector}）"
        else:
            print(f"- {NA}（该 ticker 无历史交易记录，且无法确定 Sector 以退化）")
            return
        print(f"- 该 ticker 无历史记录 → 退化为 {scope}")
    if not mine:
        print(f"- {NA}（{scope} 亦无历史记录）")
        return
    print(f"- 样本数：{len(mine)}（{scope}）")
    print()
    print("| Date | Ticker | Tag | Score | Price |")
    print("|---|---|---|---|---|")
    for r in sorted(mine, key=lambda x: x.get("Date") or "", reverse=True)[:8]:
        print("| {} | {} | {} | {} | {} |".format(
            r.get("Date") or NA,
            r.get("Ticker") or NA,
            r.get("Tag") or NA,
            fmt(r.get("Score")),
            fmt(r.get("Entry_Price") or r.get("Price")),
        ))


def block_macro() -> None:
    section("4. 宏观环境（macro_data.json + market_indicators.json）")
    macro = read_json(MACRO_DATA)
    if macro:
        keys = [k for k in macro.keys()][:10]
        print(f"- macro_data.json 顶层键：{', '.join(keys) if keys else NA}")
    else:
        print(f"- macro_data.json：{NA}")
    mi = read_json(MARKET_INDICATORS)
    if mi:
        print(f"- market_indicators.json 顶层键：{', '.join(list(mi.keys())[:10]) or NA}")
        assets = mi.get("assets") if isinstance(mi.get("assets"), (list, dict)) else None
        if isinstance(assets, dict):
            sample = list(assets.items())[:3]
        elif isinstance(assets, list):
            sample = [(a.get("symbol") or a.get("name"), a.get("price") or a.get("last"))
                      for a in assets[:3] if isinstance(a, dict)]
        else:
            sample = []
        for name, val in sample:
            print(f"  - {name or NA}：{fmt(val) if not isinstance(val, dict) else NA}")
    else:
        print(f"- market_indicators.json：{NA}")


# ---------------------------------------------------------------- 主流程
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="单只 ticker 的结构化简报（只读）")
    ap.add_argument("ticker", help="股票代码，如 AAPL")
    ap.add_argument("--date", default=None, help="指定 Scan_Date（YYYY-MM-DD），默认最新")
    args = ap.parse_args(argv)

    ticker = (args.ticker or "").strip().upper()
    if not ticker:
        print("ticker 为空")
        return 0

    print(f"# Ticker Brief: {ticker}")
    print()
    print(f"- 仓库：{REPO.name}")
    print(f"- 指定日期：{args.date or '（最新）'}")
    print(f"- 数据依赖：ai_snapshot.csv / quant_factor_snapshot.csv / trade_history.csv / "
          f"macro_data.json / market_indicators.json")

    block_ai(ticker)
    block_quant(ticker, args.date)
    block_history(ticker)
    block_macro()

    print()
    print("---")
    print("说明：本简报只读，不写文件；缺失项统一显示 N/A。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
