#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research-only low-frequency ATR strategy validation; never touches production."""
from __future__ import annotations
import argparse, math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO / "research_backtest_sp500_pit_2y.csv"
DEFAULT_OUTPUT = REPO / "docs" / "LOW_FREQUENCY_ATR_STRATEGY.md"
FACTOR, RETURN_COL, HORIZON = "ATR_Pct", "Forward_Return_20D", 20
REBALANCE_EVERY, PURGE_DATES, MIN_NAMES = 20, 20, 30
TOP_FRACTION, COST_BPS = 0.20, (5.0, 10.0, 20.0, 50.0)

def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"Ticker", "Scan_Date", FACTOR, RETURN_COL}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    d = frame[["Ticker", "Scan_Date", FACTOR, RETURN_COL]].copy()
    d["Ticker"] = d["Ticker"].astype(str).str.strip().str.upper()
    d["Scan_Date"] = pd.to_datetime(d["Scan_Date"], errors="coerce").dt.normalize()
    for c in (FACTOR, RETURN_COL):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=["Ticker", "Scan_Date", FACTOR, RETURN_COL])
    d = d[(d["Ticker"] != "") & (d[RETURN_COL] > -1)]
    if d.duplicated(["Scan_Date", "Ticker"]).any():
        raise ValueError(f"duplicate Scan_Date/Ticker rows: {int(d.duplicated(['Scan_Date','Ticker']).sum())}")
    return d.sort_values(["Scan_Date", "Ticker"]).reset_index(drop=True)

def valid_dates(d: pd.DataFrame) -> list[pd.Timestamp]:
    counts = d.groupby("Scan_Date")["Ticker"].nunique()
    return sorted(counts[counts >= MIN_NAMES].index.tolist())

def chronological_splits(dates: list[pd.Timestamp], purge_dates: int = PURGE_DATES):
    dates = sorted(pd.Timestamp(x).normalize() for x in dates)
    if len(dates) < 100:
        raise ValueError(f"need at least 100 valid signal dates; got {len(dates)}")
    a, b = int(len(dates)*0.60), int(len(dates)*0.80)
    result = {"train": dates[:a], "validation": dates[a+purge_dates:b], "test": dates[b+purge_dates:]}
    if any(not v for v in result.values()):
        raise ValueError("chronological split produced an empty segment")
    return result

def daily_groups(d: pd.DataFrame, dates: list[pd.Timestamp], direction: int):
    rows = []
    for date, day in d[d["Scan_Date"].isin(dates)].groupby("Scan_Date", sort=True):
        day = day.dropna(subset=[FACTOR, RETURN_COL]).sort_values("Ticker").copy()
        if day["Ticker"].nunique() < MIN_NAMES:
            continue
        n = max(1, int(math.ceil(len(day)*TOP_FRACTION)))
        day["_rank"] = day[FACTOR].rank(method="first", ascending=True)
        chosen = day.nlargest(n, "_rank") if direction > 0 else day.nsmallest(n, "_rank")
        rows.append({"date": pd.Timestamp(date), "tickers": frozenset(chosen["Ticker"]),
                     "gross": float(chosen[RETURN_COL].mean()),
                     "benchmark": float(day[RETURN_COL].mean())})
    return rows

def non_overlapping(rows):
    return rows[::REBALANCE_EVERY]

def metrics(rows: list[dict[str, Any]], cost_bps: float):
    if not rows:
        return {"n": 0, "gross_mean_pct": None, "net_mean_pct": None, "benchmark_mean_pct": None,
                "excess_mean_pct": None, "win_rate_pct": None, "sharpe": None,
                "max_drawdown_pct": None, "turnover_pct": None}
    gross, net, bench, excess, turns = [], [], [], [], []
    prev = None
    for r in rows:
        current = r["tickers"]
        turnover = 1.0 if prev is None else 1.0-len(prev & current)/max(1, len(prev))
        turnover = min(1.0, max(0.0, turnover))
        nr = r["gross"] - turnover*cost_bps/10000.0
        gross.append(r["gross"]); net.append(nr); bench.append(r["benchmark"])
        excess.append(nr-r["benchmark"]); turns.append(turnover); prev = current
    arr = np.asarray(net); sd = float(np.std(arr, ddof=1)) if len(arr)>1 else float("nan")
    sharpe = float(np.mean(arr)/sd*math.sqrt(252/HORIZON)) if len(arr)>1 and math.isfinite(sd) and sd>0 else None
    wealth = np.cumprod(1+arr); peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return {"n":len(rows), "gross_mean_pct":float(np.mean(gross)*100), "net_mean_pct":float(np.mean(net)*100),
            "benchmark_mean_pct":float(np.mean(bench)*100), "excess_mean_pct":float(np.mean(excess)*100),
            "win_rate_pct":float(np.mean(arr>0)*100), "sharpe":sharpe,
            "max_drawdown_pct":float(np.min(wealth/peaks-1)*100), "turnover_pct":float(np.mean(turns)*100)}

def choose_direction(d, train_dates):
    hi, lo = non_overlapping(daily_groups(d, train_dates, 1)), non_overlapping(daily_groups(d, train_dates, -1))
    if min(len(hi), len(lo)) < 3:
        raise ValueError("training segment has fewer than 3 non-overlapping observations")
    spread = float(np.mean([x["gross"] for x in hi])-np.mean([x["gross"] for x in lo]))
    return (1 if spread > 0 else -1), spread

def evaluate(d, dates, direction, cost_bps=10.0):
    rows = non_overlapping(daily_groups(d, dates, direction))
    out = metrics(rows, cost_bps)
    out["direction"] = "HIGH_ATR" if direction > 0 else "LOW_ATR"
    out["valid_signal_dates"] = len(dates)
    return out

def run_research(frame):
    d = clean_frame(frame); dates = valid_dates(d); splits = chronological_splits(dates)
    direction, train_spread = choose_direction(d, splits["train"])
    segments = {name:evaluate(d, ds, direction, 10.0) for name, ds in splits.items()}
    costs = {str(int(c)):evaluate(d, splits["test"], direction, c) for c in COST_BPS}
    test = segments["test"]; verdict = "NOT_ENOUGH_TEST_OBSERVATIONS"
    if test["n"] >= 8:
        verdict = "PRELIMINARY_POSITIVE_ONLY" if test["net_mean_pct"] > 0 and test["excess_mean_pct"] > 0 else "NOT_CONFIRMED"
    return {"rows":len(d), "tickers":int(d.Ticker.nunique()), "dates":len(dates),
            "start":dates[0].strftime("%Y-%m-%d"), "end":dates[-1].strftime("%Y-%m-%d"),
            "direction":"HIGH_ATR" if direction>0 else "LOW_ATR", "train_spread_pct":train_spread*100,
            "segments":segments, "costs":costs, "verdict":verdict}

def render_report(r):
    def f(v):
        return "N/A" if v is None or not math.isfinite(float(v)) else f"{float(v):+.3f}"
    lines = [
        "# 低频 ATR 因子策略研究（研究层，不接生产）", "",
        f"> 数据：research_backtest_sp500_pit_2y.csv；{r['rows']:,} 行、{r['tickers']} 个 ticker、{r['dates']} 个有效信号日。",
        f"> 日期：{r['start']} 至 {r['end']}；因子 ATR_Pct；持有期 20 个交易日。",
        "> 限制：前瞻标签为历史收盘到未来收盘，不含真实开盘成交、止损路径、公司行动、退市处理或市场冲击；数据也不是盲测集。",
        "", "## 固定方法", "",
        "- 时间顺序 60% 训练 / 20% 验证 / 20% 测试；边界清除 20 个信号日，防止 20D 标签跨段。",
        "- 只用训练段决定方向；验证和测试冻结方向，不重新挑因子方向。",
        "- 每约 20 个有效信号日取一个观测，降低前瞻收益重叠偏差。",
        "- 每期等权持有 ATR 横截面最高或最低 20%，与同日全股票等权基准比较。",
        "- 成本按单边换手率 × 单边成本假设；测试段敏感性为 5/10/20/50 bps。",
        "", "## 冻结方向", "", f"- 训练段方向：**{r['direction']}**",
        f"- 训练段高 ATR 减低 ATR 非重叠平均收益差：**{f(r['train_spread_pct'])}%**",
        "", "## 分段结果（成本 10 bps × 单边换手率）", "",
        "| 区间 | 信号日 | 非重叠观察 | 毛均收益 | 净均收益 | 等权基准 | 净超额 | 胜率 | 年化 Sharpe* | 最大回撤 | 换手 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for name, label in (("train","训练"),("validation","验证"),("test","测试")):
        m=r["segments"][name]
        lines.append(f"| {label} | {m['valid_signal_dates']} | {m['n']} | {f(m['gross_mean_pct'])}% | {f(m['net_mean_pct'])}% | {f(m['benchmark_mean_pct'])}% | {f(m['excess_mean_pct'])}% | {f(m['win_rate_pct'])}% | {f(m['sharpe'])} | {f(m['max_drawdown_pct'])}% | {f(m['turnover_pct'])}% |")
    lines += ["", "*Sharpe 用非重叠 20D 收益观察年化；样本少时仍不稳定。", "",
              "## 测试期成本敏感性", "", "| 单边成本 | 观察数 | 净均收益 | 净超额 | Sharpe |", "|---:|---:|---:|---:|---:|"]
    for c,m in r["costs"].items():
        lines.append(f"| {c} bps | {m['n']} | {f(m['net_mean_pct'])}% | {f(m['excess_mean_pct'])}% | {f(m['sharpe'])} |")
    lines += ["", "## 判定", "", f"**{r['verdict']}**", "",
              "- PRELIMINARY_POSITIVE_ONLY 只表示测试段净收益和净超额均为正且至少有 8 个非重叠观察，不等于证明 alpha。",
              "- 不做参数搜索，不使用验证/测试段挑方向，不改生产评分、Scan、止损或交易账本。",
              "- 通过后仍需真实 OHLCV、下一交易日开盘成交、实际止损路径、公司行动/退市和可交易股票池验证。", ""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=DEFAULT_INPUT); p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    a=p.parse_args()
    if not a.input.exists(): raise SystemExit(f"missing input data: {a.input}")
    result=run_research(pd.read_csv(a.input,dtype=str,keep_default_na=False))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(render_report(result),encoding="utf-8")
    print(f"rows={result['rows']} tickers={result['tickers']} dates={result['dates']} direction={result['direction']} verdict={result['verdict']}")
    print(f"report={a.output}")
if __name__=="__main__": main()
