#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research-only execution-timing check for ATR selection.

Signals use factors known after Technical_Date close. Entry is the next session's
Open on Scan_Date; exit is that session's Close after HOLD_SESSIONS sessions.
This deliberately does not change production strategy or the existing close-close
research labels. The refreshed workflow uses yfinance auto-adjusted OHLC; provider
history and symbol-transition limitations still apply.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = REPO / "research_factor_snapshots_sp500_pit_10y.csv"
DEFAULT_PRICES = REPO / "research_price_history_sp500_10y.csv"
DEFAULT_CONSTITUENTS = REPO / "tools" / "research" / "data" / "sp500_components_history.csv"
DEFAULT_OUTPUT = REPO / "LOW_FREQUENCY_ATR_EXECUTION_10Y.md"
FACTOR = "ATR_Pct"
HOLD_SESSIONS = 20
PURGE_DATES = 20
MIN_NAMES = 30
TOP_FRACTION = 0.20
COST_BPS = (5.0, 10.0, 20.0, 50.0)


def load_inputs(snapshot: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    required_snap = {"Ticker", "Scan_Date", "Technical_Date", FACTOR}
    required_price = {"Date", "Ticker", "Open", "Close"}
    missing = sorted(required_snap - set(snapshot.columns))
    if missing:
        raise ValueError(f"snapshot missing required columns: {missing}")
    missing = sorted(required_price - set(prices.columns))
    if missing:
        raise ValueError(f"price history missing required columns: {missing}")

    s = snapshot[["Ticker", "Scan_Date", "Technical_Date", FACTOR]].copy()
    s["Ticker"] = s["Ticker"].astype(str).str.strip().str.upper()
    s["Scan_Date"] = pd.to_datetime(s["Scan_Date"], errors="coerce").dt.normalize()
    s["Technical_Date"] = pd.to_datetime(s["Technical_Date"], errors="coerce").dt.normalize()
    s[FACTOR] = pd.to_numeric(s[FACTOR], errors="coerce")
    s = s.dropna(subset=["Ticker", "Scan_Date", "Technical_Date", FACTOR])
    s = s[(s["Ticker"] != "") & (s["Technical_Date"] < s["Scan_Date"])]
    if s.duplicated(["Scan_Date", "Ticker"]).any():
        raise ValueError("duplicate snapshot Scan_Date/Ticker rows")

    p = prices[["Date", "Ticker", "Open", "Close"]].copy()
    p["Ticker"] = p["Ticker"].astype(str).str.strip().str.upper()
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce").dt.normalize()
    for col in ("Open", "Close"):
        p[col] = pd.to_numeric(p[col], errors="coerce")
    p = p.dropna(subset=["Date", "Ticker"])
    if p.duplicated(["Date", "Ticker"]).any():
        raise ValueError("duplicate price Date/Ticker rows")
    by_ticker = {tk: g.sort_values("Date").reset_index(drop=True) for tk, g in p.groupby("Ticker")}
    return s.sort_values(["Scan_Date", "Ticker"]).reset_index(drop=True), by_ticker


def attach_execution_returns(snapshot: pd.DataFrame, by_ticker: dict[str, pd.DataFrame],
                             hold_sessions: int = HOLD_SESSIONS) -> tuple[pd.DataFrame, dict[str, int]]:
    """Entry at Scan_Date Open; exit at Close of the Nth held session."""
    out = snapshot.copy()
    out["Execution_Return"] = np.nan
    stats = {"rows_in": len(out), "no_ticker_prices": 0, "missing_entry_bar": 0,
             "missing_or_invalid_open": 0, "insufficient_exit_history": 0,
             "missing_or_invalid_exit_close": 0, "date_alignment_mismatch": 0}
    for idx, row in out.iterrows():
        bars = by_ticker.get(row["Ticker"])
        if bars is None or bars.empty:
            stats["no_ticker_prices"] += 1
            continue
        dates = pd.DatetimeIndex(bars["Date"])
        pos = int(dates.searchsorted(row["Technical_Date"], side="right"))
        if pos >= len(bars):
            stats["missing_entry_bar"] += 1
            continue
        # Avoid silently shifting execution to a later session than the recorded signal date.
        if bars.iloc[pos]["Date"] != row["Scan_Date"]:
            stats["date_alignment_mismatch"] += 1
            continue
        entry_open = bars.iloc[pos]["Open"]
        if pd.isna(entry_open) or not np.isfinite(entry_open) or entry_open <= 0:
            stats["missing_or_invalid_open"] += 1
            continue
        exit_pos = pos + hold_sessions - 1
        if exit_pos >= len(bars):
            stats["insufficient_exit_history"] += 1
            continue
        exit_close = bars.iloc[exit_pos]["Close"]
        if pd.isna(exit_close) or not np.isfinite(exit_close) or exit_close <= 0:
            stats["missing_or_invalid_exit_close"] += 1
            continue
        out.at[idx, "Execution_Return"] = float(exit_close / entry_open - 1.0)
    stats["rows_valid"] = int(out["Execution_Return"].notna().sum())
    return out, stats


def valid_dates(d: pd.DataFrame) -> list[pd.Timestamp]:
    counts = d.groupby("Scan_Date")["Ticker"].nunique()
    return sorted(counts[counts >= MIN_NAMES].index.tolist())


def chronological_splits(dates: list[pd.Timestamp]) -> dict[str, list[pd.Timestamp]]:
    dates = sorted(pd.Timestamp(x).normalize() for x in dates)
    if len(dates) < 100:
        raise ValueError(f"need at least 100 valid signal dates; got {len(dates)}")
    a, b = int(len(dates) * 0.60), int(len(dates) * 0.80)
    result = {"train": dates[:a], "validation": dates[a + PURGE_DATES:b],
              "test": dates[b + PURGE_DATES:]}
    if any(not part for part in result.values()):
        raise ValueError("chronological split produced an empty segment")
    return result


def portfolio_rows(d: pd.DataFrame, dates: list[pd.Timestamp], direction: int) -> list[dict[str, Any]]:
    rows = []
    subset = d[d["Scan_Date"].isin(dates)]
    for date, day in subset.groupby("Scan_Date", sort=True):
        day = day.dropna(subset=[FACTOR, "Execution_Return"]).sort_values("Ticker").copy()
        if day["Ticker"].nunique() < MIN_NAMES:
            continue
        n = max(1, int(math.ceil(len(day) * TOP_FRACTION)))
        day["_rank"] = day[FACTOR].rank(method="first", ascending=True)
        chosen = day.nlargest(n, "_rank") if direction > 0 else day.nsmallest(n, "_rank")
        rows.append({"date": pd.Timestamp(date), "tickers": frozenset(chosen["Ticker"]),
                     "gross": float(chosen["Execution_Return"].mean()),
                     "benchmark": float(day["Execution_Return"].mean())})
    return rows[::HOLD_SESSIONS]


def metrics(rows: list[dict[str, Any]], cost_bps: float) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "gross_mean_pct": None, "net_mean_pct": None,
                "benchmark_mean_pct": None, "excess_mean_pct": None,
                "win_rate_pct": None, "sharpe": None, "max_drawdown_pct": None,
                "turnover_pct": None}
    gross, net, benchmark, excess, turnover_list = [], [], [], [], []
    prev = None
    for row in rows:
        current = row["tickers"]
        turnover = 1.0 if prev is None else 1.0 - len(prev & current) / max(1, len(prev))
        turnover = min(1.0, max(0.0, turnover))
        net_return = row["gross"] - turnover * cost_bps / 10000.0
        gross.append(row["gross"])
        net.append(net_return)
        benchmark.append(row["benchmark"])
        excess.append(net_return - row["benchmark"])
        turnover_list.append(turnover)
        prev = current
    arr = np.asarray(net, dtype=float)
    sd = float(np.std(arr, ddof=1)) if len(arr) > 1 else float("nan")
    sharpe = float(np.mean(arr) / sd * math.sqrt(252 / HOLD_SESSIONS)) if len(arr) > 1 and math.isfinite(sd) and sd > 0 else None
    wealth = np.cumprod(1 + arr)
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return {"n": len(rows), "gross_mean_pct": float(np.mean(gross) * 100),
            "net_mean_pct": float(np.mean(net) * 100),
            "benchmark_mean_pct": float(np.mean(benchmark) * 100),
            "excess_mean_pct": float(np.mean(excess) * 100),
            "win_rate_pct": float(np.mean(arr > 0) * 100), "sharpe": sharpe,
            "max_drawdown_pct": float(np.min(wealth / peaks - 1) * 100),
            "turnover_pct": float(np.mean(turnover_list) * 100)}


def run_research(snapshot: pd.DataFrame, prices: pd.DataFrame) -> dict[str, Any]:
    s, by_ticker = load_inputs(snapshot, prices)
    d, audit = attach_execution_returns(s, by_ticker)
    d = d.dropna(subset=["Execution_Return"]).copy()
    dates = valid_dates(d)
    splits = chronological_splits(dates)
    hi = portfolio_rows(d, splits["train"], 1)
    lo = portfolio_rows(d, splits["train"], -1)
    if min(len(hi), len(lo)) < 3:
        raise ValueError("training segment has fewer than 3 non-overlapping observations")
    spread = float(np.mean([x["gross"] for x in hi]) - np.mean([x["gross"] for x in lo]))
    direction = 1 if spread > 0 else -1
    segments = {name: metrics(portfolio_rows(d, ds, direction), 10.0)
                for name, ds in splits.items()}
    costs = {str(int(c)): metrics(portfolio_rows(d, splits["test"], direction), c)
             for c in COST_BPS}
    test = segments["test"]
    verdict = "NOT_ENOUGH_TEST_OBSERVATIONS"
    if test["n"] >= 8:
        verdict = "PRELIMINARY_POSITIVE_ONLY" if test["net_mean_pct"] > 0 and test["excess_mean_pct"] > 0 else "NOT_CONFIRMED"
    return {"rows": len(d), "tickers": int(d["Ticker"].nunique()), "dates": len(dates),
            "start": dates[0].strftime("%Y-%m-%d"), "end": dates[-1].strftime("%Y-%m-%d"),
            "direction": "HIGH_ATR" if direction > 0 else "LOW_ATR", "train_spread_pct": spread * 100,
            "segments": segments, "costs": costs, "verdict": verdict, "audit": audit}


def render_report(r: dict[str, Any], membership_has_removals: bool, price_basis: str = "not verified") -> str:
    def fmt(v: Any) -> str:
        return "N/A" if v is None or not math.isfinite(float(v)) else f"{float(v):+.3f}"
    lines = [
        "# 低频 ATR 开盘入场执行验证（研究层，不接生产）", "",
        f"> 数据：{r['rows']:,} 个可计算样本，{r['tickers']} 个 ticker，{r['dates']} 个有效信号日。",
        f"> 日期：{r['start']} 至 {r['end']}；因子 ATR_Pct；入场为信号日开盘，持有 {HOLD_SESSIONS} 个交易日并在第 20 个交易日收盘退出。",
        "> 与旧报告的收盘到收盘标签不同：此报告使用开盘入场和持有期末收盘，独立计算收益，不复用 Forward_Return_20D。",
        f"> 价格源：{price_basis}。即使使用复权 OHLC，也不能保证数据供应商的公司行动历史完全正确。",
        f"> 股票池限制：{'使用了带 date_removed 的历史有效期数据' if membership_has_removals else '缺少 date_removed，存在明显幸存者偏差；该样本不能称为严格 PIT 股票池'}。上游带星号日期是近似值，ticker 更名/重用仍需审计。",
        "", "## 数据对齐审计", "",
        "| 项目 | 行数 |", "|---|---:|",
    ]
    for key, label in [
        ("rows_in", "输入快照行"), ("no_ticker_prices", "无该 ticker 价格"),
        ("missing_entry_bar", "无入场日价格"), ("missing_or_invalid_open", "无效开盘价"),
        ("insufficient_exit_history", "持有期历史不足"), ("missing_or_invalid_exit_close", "无效退出收盘价"),
        ("date_alignment_mismatch", "信号日与价格日不一致"), ("rows_valid", "有效执行收益样本")
    ]:
        lines.append(f"| {label} | {r['audit'].get(key, 0):,} |")
    lines += ["", "## 冻结方向", "", f"- 训练集方向：**{r['direction']}**",
              f"- 训练集高 ATR 减低 ATR 非重叠平均收益差：**{fmt(r['train_spread_pct'])}%**",
              "", "## 分段结果（成本 10 bps × 单边换手率）", "",
              "| 区间 | 非重叠观察 | 毛均收益 | 净均收益 | 等权基准 | 净超额 | 胜率 | 年化 Sharpe | 最大回撤 | 换手 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, label in (("train", "训练"), ("validation", "验证"), ("test", "测试")):
        m = r["segments"][name]
        lines.append(f"| {label} | {m['n']} | {fmt(m['gross_mean_pct'])}% | {fmt(m['net_mean_pct'])}% | {fmt(m['benchmark_mean_pct'])}% | {fmt(m['excess_mean_pct'])}% | {fmt(m['win_rate_pct'])}% | {fmt(m['sharpe'])} | {fmt(m['max_drawdown_pct'])}% | {fmt(m['turnover_pct'])}% |")
    lines += ["", "## 测试期成本敏感性", "",
              "| 单边成本 | 观察数 | 净均收益 | 净超额 | Sharpe |", "|---:|---:|---:|---:|---:|"]
    for cost, m in r["costs"].items():
        lines.append(f"| {cost} bps | {m['n']} | {fmt(m['net_mean_pct'])}% | {fmt(m['excess_mean_pct'])}% | {fmt(m['sharpe'])} |")
    lines += ["", "## 判定", "", f"**{r['verdict']}**", "",
              "- 该结果仅用于检查成交时点对 ATR 结论的影响；即使结果为正，也不证明 alpha。",
              "- 当前价格未复权，且若成分文件无退出日期，则存在公司行动与幸存者偏差。",
              "- 生产使用前必须接入拆股/分红调整数据和有加入、退出日期的历史成分表，并用真实可交易约束复验。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--constituents", type=Path, default=DEFAULT_CONSTITUENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.snapshot.exists():
        raise SystemExit(f"missing snapshot: {args.snapshot}")
    if not args.prices.exists():
        raise SystemExit(f"missing price history: {args.prices}")
    snapshot = pd.read_csv(args.snapshot, dtype=str, keep_default_na=False)
    prices = pd.read_csv(args.prices, dtype=str, keep_default_na=False)
    result = run_research(snapshot, prices)
    membership_has_removals = False
    if args.constituents.exists():
        const = pd.read_csv(args.constituents, dtype=str, keep_default_na=False)
        membership_has_removals = "date_removed" in {str(col).strip().lower() for col in const.columns}
    basis_values = sorted({
        str(value).strip() for value in prices.get("Price_Basis", pd.Series(dtype=str)).dropna()
        if str(value).strip()
    })
    price_basis = (
        "yfinance auto_adjust=True（OHLC 已复权）"
        if basis_values == ["yfinance_auto_adjusted"]
        else "未验证（输入 CSV 缺少一致的 Price_Basis 标记）"
    )
    report = render_report(result, membership_has_removals, price_basis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"rows={result['rows']} tickers={result['tickers']} dates={result['dates']} direction={result['direction']} verdict={result['verdict']}")
    print(f"valid_execution_returns={result['audit']['rows_valid']} audit={result['audit']}")
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
