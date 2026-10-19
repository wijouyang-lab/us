#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 3 阶段一：基本面因子最小 PIT 管线（小样本 50 只）。

数据源：**yfinance**（已在 requirements-production.txt pin >=1.0,<2，本轮**不新增依赖**）
指标：  PE_Proxy / PB_Proxy / ROE_Proxy（季度报表推导，非 yfinance 现成字段）
PIT 策略：
  · yfinance 免费层**不提供财报发布日**（release date），只给**报告期**（period end）。
  · 因此采用**保守滞后**：任何一期财报，只在其 period_end + RELEASE_LAG_DAYS(90) 之后才被视为可用。
  · 日频对齐：把"可用财报值"按 dates 向后填充（ffill），再与每个交易日对齐。
  · ⇒ 这是**PIT 近似**（release date proxy），不是严格 PIT；报告与 CSV 均记录该假设。
输出：research_fundamentals_pit_sample.csv（Date, Ticker, Factor_Name, Value, Period_End, Release_Proxy）

用法：
  python tools/research/fetch_fundamentals_pit.py            # 50 只
  python tools/research/fetch_fundamentals_pit.py --limit 10
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
CONSTITUENTS = REPO / "sp500_constituents.csv"
OUT = REPO / "research_fundamentals_pit_sample.csv"
RELEASE_LAG_DAYS = 90       # 财报发布日代理滞后
MAX_RETRIES = 3
SLEEP_BETWEEN = 1.2


def load_universe(limit: int) -> list[str]:
    if not CONSTITUENTS.exists():
        raise SystemExit(f"missing {CONSTITUENTS}")
    df = pd.read_csv(CONSTITUENTS, dtype=str)
    tickers = [str(t).strip().upper() for t in df["Ticker"].tolist() if str(t).strip()]
    return tickers[:limit]


def _series(df: pd.DataFrame, *names):
    """从 yfinance 的 quarterly_* DataFrame 中取第一行匹配项（行名大小写/写法不一）。"""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for want in names:
        for idx in df.index:
            if str(idx).strip().lower() == want.lower():
                return df.loc[idx]
    return None


def fetch_one(ticker: str) -> list[dict]:
    """返回该 ticker 的季度基本面记录（含 period_end / release proxy）。"""
    import yfinance as yf

    rows: list[dict] = []
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tk = yf.Ticker(ticker)
            qf = getattr(tk, "quarterly_financials", None)
            qbs = getattr(tk, "quarterly_balance_sheet", None)
            if qf is None or qf.empty:
                return rows

            net_income = _series(qf, "NetIncome", "Net Income", "NetIncomeCommonStockholders")
            equity = _series(qbs, "StockholdersEquity", "TotalStockHolderEquity",
                             "CommonStockEquity") if qbs is not None else None
            shares = _series(qbs, "OrdinarySharesNumber", "ShareIssued") if qbs is not None else None
            assets = _series(qbs, "TotalAssets") if qbs is not None else None

            for col in qf.columns:
                period_end = pd.Timestamp(col)
                rec = {
                    "Period_End": period_end.strftime("%Y-%m-%d"),
                    "Release_Proxy": (period_end + timedelta(days=RELEASE_LAG_DAYS)).strftime("%Y-%m-%d"),
                }
                vals = {}
                if net_income is not None and col in net_income.index:
                    vals["NetIncome"] = float(net_income[col]) if pd.notna(net_income[col]) else None
                if equity is not None and col in equity.index:
                    vals["Equity"] = float(equity[col]) if pd.notna(equity[col]) else None
                if shares is not None and col in shares.index:
                    vals["Shares"] = float(shares[col]) if pd.notna(shares[col]) else None
                if assets is not None and col in assets.index:
                    vals["Assets"] = float(assets[col]) if pd.notna(assets[col]) else None
                rec.update(vals)
                rows.append(rec)
            return rows
        except Exception as e:
            print(f"  [retry {attempt}/{MAX_RETRIES}] {ticker}: {type(e).__name__}: {e}")
            time.sleep(SLEEP_BETWEEN * attempt)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args(argv)

    tickers = load_universe(args.limit)
    print(f"universe: {len(tickers)} tickers（{tickers[:5]} …）")
    print(f"source: yfinance（已 pin >=1.0,<2）; release lag = {RELEASE_LAG_DAYS}d")

    all_rows: list[dict] = []
    ok = fail = 0
    for i, t in enumerate(tickers, 1):
        recs = fetch_one(t)
        if recs:
            for r in recs:
                r["Ticker"] = t
            all_rows.extend(recs)
            ok += 1
        else:
            fail += 1
        if i % 10 == 0:
            print(f"  [{i}/{len(tickers)}] ok={ok} empty/fail={fail}")
        time.sleep(SLEEP_BETWEEN)

    if not all_rows:
        print("❌ 未取到任何季度基本面数据（数据源可能不可用）")
        return 1

    q = pd.DataFrame(all_rows)
    print(f"quarterly rows = {len(q)}（ok={ok} / fail={fail}）")

    # 由季度报表推导因子（每股口径）
    q["EPS_q"] = q["NetIncome"] / q["Shares"]
    q["BPS_q"] = q["Equity"] / q["Shares"]
    q["EPS_TTM"] = q.groupby("Ticker")["EPS_q"].transform(lambda s: s.rolling(4, min_periods=4).sum())
    q["BPS"] = q["BPS_q"]
    q["ROE_Proxy"] = q["NetIncome"] / q["Equity"]

    # 日频对齐：以该 ticker 的 Release_Proxy 向后 ffill（PIT 近似）
    out_rows: list[dict] = []
    for tk, g in q.groupby("Ticker"):
        g = g.sort_values("Release_Proxy")
        g = g.dropna(subset=["Release_Proxy"])
        if g.empty:
            continue
        idx = pd.to_datetime(g["Release_Proxy"])
        for factor, col in (("PE_Proxy", "EPS_TTM"), ("PB_Proxy", "BPS"), ("ROE_Proxy", "ROE_Proxy")):
            s = pd.Series(g[col].values, index=idx).dropna()
            if s.empty:
                continue
            for d, v in s.items():
                out_rows.append({"Date": d.strftime("%Y-%m-%d"), "Ticker": tk,
                                 "Factor_Name": factor, "Value": float(v)})

    if not out_rows:
        print("❌ 无可用因子行（EPS/BPS 无法推导）")
        return 1

    out = pd.DataFrame(out_rows)
    # 合并 Period_End 说明（同一 release 点可能对应多期，取最近）
    out = out.sort_values(["Date", "Ticker", "Factor_Name"]).reset_index(drop=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"written: {OUT} ({len(out)} rows, {OUT.stat().st_size} bytes)")
    print(out.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
