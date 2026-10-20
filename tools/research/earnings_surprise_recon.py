#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件驱动侦察：财报超预期（Earnings Surprise）后的超额收益。

数据（全部 yfinance 免费接口，无需 Key）：
  yf.Ticker(t).get_earnings_dates(limit=12)  → EPS Estimate / Reported EPS / Surprise(%)
  yf.Ticker(t).history(start, end)            → 个股与 SPY 收盘价

方法：
  ① Surprise% = (Reported − Estimate) / |Estimate| × 100
  ② 事件后收益：T+1 买入（收盘），持有 5 / 20 个交易日
  ③ **超额收益 = 个股收益 − SPY 同期收益**（剔除大盘 beta ✓）
  ④ 分组对比：Surprise > 5% vs Surprise < −5% vs 全样本

输出：docs/EARNINGS_SURPRISE_RECON.md（同时打印到 stdout 供 CI 日志）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
CONST = REPO / "sp500_constituents.csv"
OUT = REPO / "docs" / "EARNINGS_SURPRISE_RECON.md"

N_TICKERS = 300
YEARS_BACK = 5
HORIZONS = (5, 20)
SURPRISE_HI = 5.0
SURPRISE_LO = -5.0
SLEEP = 0.4


def load_universe(n: int) -> list:
    if not CONST.exists():
        raise SystemExit(f"missing {CONST}")
    df = pd.read_csv(CONST, dtype=str)
    return [str(t).strip().upper() for t in df["Ticker"].head(n) if str(t).strip()]


def main() -> int:
    try:
        import yfinance as yf
    except Exception as e:
        print(f"[earnings] yfinance 不可用：{e}")
        return 1

    tickers = load_universe(N_TICKERS)
    end = pd.Timestamp.utcnow().tz_localize(None).normalize()
    start = end - pd.DateOffset(years=YEARS_BACK)
    print(f"[earnings] universe={len(tickers)} range={start.date()}~{end.date()}")

    # SPY 基准
    spy = yf.Ticker("SPY").history(start=str(start.date()), end=str(end.date()),
                                   auto_adjust=True)["Close"]
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    print(f"[earnings] SPY bars={len(spy)}")

    rows, failed = [], 0
    for i, tk in enumerate(tickers, 1):
        try:
            t = yf.Ticker(tk)
            ed = t.get_earnings_dates(limit=12)
            if ed is None or ed.empty:
                failed += 1
                continue
            px = t.history(start=str((start - pd.Timedelta(days=10)).date()),
                           end=str(end.date()), auto_adjust=True)["Close"]
            if px is None or px.empty:
                failed += 1
                continue
            px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
            for d, r in ed.iterrows():
                est = pd.to_numeric(r.get("EPS Estimate"), errors="coerce")
                act = pd.to_numeric(r.get("Reported EPS"), errors="coerce")
                if pd.isna(est) or pd.isna(act) or est == 0:
                    continue
                d = pd.Timestamp(d).tz_localize(None).normalize()
                if d < start or d > end:
                    continue
                idx = px.index.searchsorted(d, side="right")   # T+1 起
                if idx >= len(px):
                    continue
                for h in HORIZONS:
                    if idx + h >= len(px):
                        continue
                    sp = spy.index.searchsorted(px.index[idx], side="left")
                    if sp < 0 or sp + h >= len(spy):
                        continue
                    stock_ret = float(px.iloc[idx + h] / px.iloc[idx] - 1)
                    spy_ret = float(spy.iloc[sp + h] / spy.iloc[sp] - 1)
                    rows.append({"Ticker": tk, "Earnings_Date": d.date(),
                                 "Surprise_Pct": float((act - est) / abs(est) * 100),
                                 "Horizon": h, "Ret": stock_ret,
                                 "Excess": stock_ret - spy_ret})
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [warn] {tk}: {type(e).__name__}: {e}")
        if i % 20 == 0:
            print(f"  [{i}/{len(tickers)}] events={len(rows)} failed={failed}")
        time.sleep(SLEEP)

    if not rows:
        msg = ("# 事件驱动侦察：数据不可用\n\n"
               f"- attempted={len(tickers)} failed={failed}\n"
               "- `get_earnings_dates()` 或 price history 全部为空 ⇒ 无法统计\n")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(msg, encoding="utf-8")
        print(msg)
        return 1

    d = pd.DataFrame(rows)
    print(f"[earnings] events={len(d)} tickers={d['Ticker'].nunique()} failed={failed}")

    L = ["# 事件驱动侦察：财报超预期后的超额收益\n",
         f"> 池：SP500 前 **{N_TICKERS}** 只；窗口：过去 **{YEARS_BACK}** 年",
         f"> 样本：**{len(d)}** 个（Ticker × 财报日 × 期限），覆盖 **{d['Ticker'].nunique()}** 只票",
         f"> 口径：T+1 收盘买入，持有 5/20 交易日；**超额 = 个股 − SPY**（已剔除 beta）✓\n",
         "## 1. 分组统计\n",
         "| 分组 | 期限 | 平均超额 | 胜率 | 样本 |", "|---|---|---|---|---|"]
    groups = [
        (f"**Surprise > {SURPRISE_HI:.0f}%**（超预期）", d[d["Surprise_Pct"] > SURPRISE_HI]),
        (f"**Surprise < {SURPRISE_LO:.0f}%**（不及预期）", d[d["Surprise_Pct"] < SURPRISE_LO]),
        ("中间组（−5% ~ +5%）", d[(d["Surprise_Pct"] >= SURPRISE_LO) & (d["Surprise_Pct"] <= SURPRISE_HI)]),
        ("全样本", d),
    ]
    res = {}
    for name, g in groups:
        for h in HORIZONS:
            x = pd.to_numeric(g[g["Horizon"] == h]["Excess"], errors="coerce").dropna()
            if not len(x):
                L.append(f"| {name} | {h}D | N/A | N/A | 0 |")
                continue
            res[(name, h)] = dict(mean=float(x.mean()) * 100, win=float((x > 0).mean()) * 100, n=int(len(x)))
            L.append(f"| {name} | {h}D | **{x.mean() * 100:+.3f}%** | {float((x > 0).mean()) * 100:.1f}% | {len(x)} |")
    L.append("")

    L += ["## 2. 核心对比（超预期 − 不及预期）\n"]
    for h in HORIZONS:
        a = res.get((groups[0][0], h))
        b = res.get((groups[1][0], h))
        if a and b:
            L.append(f"- **{h}D**：超预期 {a['mean']:+.3f}% vs 不及预期 {b['mean']:+.3f}% "
                     f"⇒ **差 {a['mean'] - b['mean']:+.3f} pp**"
                     + (" ✅ 方向正确" if a["mean"] > b["mean"] else " ✗ 方向相反"))
    L.append("")

    L += ["## 3. Surprise 幅度与超额的相关性\n"]
    for h in HORIZONS:
        s = d[d["Horizon"] == h][["Surprise_Pct", "Excess"]].dropna()
        if len(s) > 10:
            ic = s.corr(method="spearman").iloc[0, 1]
            L.append(f"- {h}D：Spearman ρ(Surprise, Excess) = **{ic:+.4f}**（n={len(s)}）")
    L.append("")

    L += ["## 4. 结论\n"]
    a20 = res.get((groups[0][0], 20))
    b20 = res.get((groups[1][0], 20))
    if a20 and b20:
        diff = a20["mean"] - b20["mean"]
        L.append(f"- 20D 超预期组超额 **{a20['mean']:+.3f}%**（胜率 {a20['win']:.1f}%，n={a20['n']}）")
        L.append(f"- 20D 不及预期组超额 **{b20['mean']:+.3f}%**（胜率 {b20['win']:.1f}%，n={b20['n']}）")
        L.append(f"- **多空差 {diff:+.3f} pp**" + ("⇒ ✅ 存在事件驱动 alpha" if diff > 0 else "⇒ ✗ 方向相反"))
        L.append(f"- 成本判断：双边 0.1-0.3% ⇒ "
                 + ("**可覆盖**" if diff > 0.3 else "**无法覆盖**"))
    L += ["", "## 5. ⚠️ 限制\n",
          "1. **`EPS Estimate` 覆盖率不稳定** ⇒ 部分票被静默跳过（failed 计数见日志）✓",
          "2. 财报日**盘前/盘后**未区分 ⇒ T+1 买入可能已错过首日跳空 ✓",
          "3. 未扣成本；样本集中在 100 只大盘股 ⇒ **幸存者偏差** ✓",
          "4. 2 年窗口 ⇒ 每票仅 ~8 个事件，**样本量小** ✓",
          ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\n[earnings] written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
