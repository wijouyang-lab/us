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
TXN = REPO / "portfolio_50000_transactions.csv"
TXN_TIME = REPO / "portfolio_50000_txn_time.csv"
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
    section("3. 交易明细（portfolio_50000_transactions.csv）")
    tx = read_csv(TXN)
    if not tx:
        print(f"- {NA}（portfolio_50000_transactions.csv 缺失或为空）")
        return
    # 实测：transactions / history / trade_history 三源的日期字段均只有日期；
    # trade_history.Date 形如 "2026-05-27 00:00:00"，时分秒恒为 00:00:00 → 等价于仅日期。
    print("- **数据源缺少精确时间，仅有日期**（三源均无 Trade_Time/Timestamp 之类字段）")

    def _sector_of(tk: str) -> str:
        for r in read_csv(QUANT_SNAPSHOT):
            if (r.get("Ticker") or "").strip().upper() == tk and r.get("Sector"):
                return r["Sector"]
        return ""

    def _sector_pool(sector: str) -> set:
        return {((r.get("Ticker") or "").strip().upper())
                for r in read_csv(QUANT_SNAPSHOT) if (r.get("Sector") or "") == sector}

    mine = [r for r in tx if (r.get("Ticker") or "").strip().upper() == ticker]
    scope = ticker
    if not mine:
        sector = _sector_of(ticker)
        if not sector:
            print(f"- {NA}（该 ticker 无成交记录，且无法确定 Sector 以退化）")
            return
        pool = _sector_pool(sector)
        mine = [r for r in tx if (r.get("Ticker") or "").strip().upper() in pool]
        scope = f"同 Sector（{sector}）"
        print(f"- 该 ticker 无成交记录 → 退化为 {scope}")
        if not mine:
            print(f"- {NA}（{scope} 亦无成交记录）")
            return

    # 侧车：按 Txn_ID 关联精确时刻
    tmap = {}
    for r in read_csv(TXN_TIME):
        tid = (r.get("Txn_ID") or "").strip()
        if tid and r.get("Execution_Time"):
            tmap[tid] = r["Execution_Time"]
    if tmap:
        print(f"- 侧车命中：{sum(1 for r in mine if (r.get('Txn_ID') or '') in tmap)}/{len(mine)} 条有精确时刻")
    else:
        print(f"- {NA}（无 {TXN_TIME.name} 侧车，时刻不可得）")

    print(f"- 样本数：{len(mine)}（{scope}）")
    print()
    print("| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(mine, key=lambda x: x.get("Date") or "", reverse=True)[:10]:
        action = (r.get("Action") or "").strip().upper()
        action_cn = {"BUY": "买入", "SELL": "卖出"}.get(action, action or NA)
        when = tmap.get((r.get("Txn_ID") or "").strip()) or f"{r.get('Date') or NA}（仅日期）"
        print("| {} | {} | {} | {} | {} | {} | {} |".format(
            when,
            r.get("Ticker") or NA,
            action_cn,
            fmt(r.get("Price")),
            fmt(r.get("Shares"), 0),
            fmt(r.get("Amount")),
            fmt(r.get("Realized_PnL")),
        ))

    hist = [r for r in read_csv(TRADE_HISTORY)
            if (r.get("Ticker") or "").strip().upper() == ticker]
    if hist:
        print()
        print("补充：历史推荐与退出（trade_history.csv，仅日期）")
        print()
        print("| Date | Tag | Score | Price | Exit_Date | Exit_Price | Status |")
        print("|---|---|---|---|---|---|---|")
        for r in sorted(hist, key=lambda x: x.get("Date") or "", reverse=True)[:5]:
            print("| {} | {} | {} | {} | {} | {} | {} |".format(
                (r.get("Date") or NA).split(" ")[0],
                r.get("Tag") or NA,
                fmt(r.get("Score")),
                fmt(r.get("Price")),
                r.get("Exit_Date") or NA,
                fmt(r.get("Exit_Price")),
                r.get("Status") or NA,
            ))


FG_CN = {
    "extreme fear": "极度恐惧", "fear": "恐惧", "neutral": "中性",
    "greed": "贪婪", "extreme greed": "极度贪婪",
}
SENT_CN = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}


def block_macro() -> None:
    section("4. 宏观环境（结论化）")

    # ---- 4.1 恐惧贪婪（market_indicators.fear_greed）----
    mi = read_json(MARKET_INDICATORS)
    fg = mi.get("fear_greed") if isinstance(mi.get("fear_greed"), dict) else {}
    score = num(fg.get("score"))
    rating = (fg.get("rating") or "").strip().lower()
    if score is None:
        print(f"- 恐惧贪婪指数：{NA}")
    else:
        print(f"- 恐惧贪婪指数：**{score:.2f}（{FG_CN.get(rating, rating or NA)}）**"
              f"　时间戳：{fg.get('timestamp') or NA}")

    # ---- 4.2 FedWatch（market_indicators.fedwatch）----
    fw = mi.get("fedwatch") if isinstance(mi.get("fedwatch"), dict) else {}
    prob = fw.get("probabilities") if isinstance(fw.get("probabilities"), dict) else {}
    parts = []
    for key, label in (("cut_25bp", "降息 25bp"), ("hold", "维持不变"),
                       ("hike_25bp", "加息 25bp"), ("cut_50bp", "降息 50bp")):
        v = num(prob.get(key))
        if v is not None:
            parts.append(f"{label} **{v:.1f}%**")
    if parts:
        print(f"- FedWatch（会议 {fw.get('next_meeting') or NA}，当前目标区间 "
              f"{fw.get('current_target') or NA}）：" + " / ".join(parts))
    else:
        print(f"- FedWatch：{NA}")

    # ---- 4.3 economic 指标（macro_data.economic 列表）----
    macro = read_json(MACRO_DATA)
    econ = macro.get("economic") if isinstance(macro.get("economic"), list) else []
    if econ:
        print(f"- 宏观指标（{len(econ)} 项，最新 {macro.get('generated_at') or NA}）：")
        for item in econ[:6]:
            if not isinstance(item, dict):
                continue
            print("  - {}：**{}**（前值 {}，{}，{}）".format(
                item.get("indicator") or NA,
                item.get("value") or NA,
                item.get("prev") or NA,
                item.get("date") or NA,
                SENT_CN.get((item.get("sentiment") or "").strip().lower(),
                            item.get("sentiment") or NA),
            ))
        cpi = [i for i in econ if isinstance(i, dict)
               and any(k in str(i.get("indicator") or "") for k in ("CPI", "通胀"))]
        if cpi:
            print(f"  - ★ CPI 同比：**{cpi[0].get('value') or NA}**"
                  f"（{cpi[0].get('date') or NA}）")
    else:
        print(f"- 宏观指标：{NA}")

    # ---- 4.4 speakers（macro_data.speakers 列表）----
    spk = macro.get("speakers") if isinstance(macro.get("speakers"), list) else []
    spk = [s for s in spk if isinstance(s, dict)]
    if spk:
        s = spk[0]
        print("- 美联储讲话：最近一次 **{}**（{}，{}）：{}　立场：**{}**".format(
            s.get("person") or NA,
            s.get("time") or NA,
            s.get("source") or NA,
            s.get("content_cn") or s.get("content") or NA,
            SENT_CN.get((s.get("sentiment") or "").strip().lower(),
                        s.get("sentiment") or NA),
        ))
        for s in spk[1:3]:
            print("  - 另有 {}（{}）：{}　[{}]".format(
                s.get("person") or NA, s.get("time") or NA,
                (s.get("content_cn") or s.get("content") or NA)[:60],
                SENT_CN.get((s.get("sentiment") or "").strip().lower(),
                            s.get("sentiment") or NA)))
    else:
        print(f"- 美联储讲话：{NA}")


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
