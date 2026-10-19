#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BP 因子 OOS（样本外）稳健性检验。

切分：按 Release_Proxy 日期排序，前 70% 为训练集，后 30% 为测试集（时间序列切分，无重叠）。
训练集：行业中性化排序 + 确定方向（Q5-Q1 为正 ⇒ 做多 Q5；为负 ⇒ 反向）。
测试集：严格沿用训练集方向，重新计 Q5/Q1、多空、Welch t、Spearman IC。
输出：docs/FACTOR_OOS_VALIDATION.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
CORR = REPO / "research_fundamentals_pit_corrected.csv"
OUT = REPO / "docs" / "FACTOR_OOS_VALIDATION.md"
FACTOR = "BP"
HORIZONS = (5, 10, 20)
Q = 5
TRAIN_FRAC = 0.70


def stats(s: pd.DataFrame, fac: str, sign: int) -> dict:
    """s 需含 Sector / fac / Pct / Q / Fwd_*D。sign=+1 表示做多高值组。"""
    out = {}
    for h in HORIZONS:
        col = f"Fwd_{h}D"
        hi, lo = (Q, 1) if sign > 0 else (1, Q)
        a = s[s["Q"] == hi][col].dropna()
        b = s[s["Q"] == lo][col].dropna()
        ls = (a.mean() - b.mean()) * 100 if len(a) and len(b) else np.nan
        if len(a) > 2 and len(b) > 2:
            se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            t = (a.mean() - b.mean()) / se if se > 0 else np.nan
        else:
            t = np.nan
        ic = s[[fac, col]].corr(method="spearman").iloc[0, 1]
        out[h] = dict(ls=ls, t=t, ic=ic, n=int(s["Pct"].notna().sum()))
    return out


def main() -> int:
    if not CORR.exists():
        raise SystemExit(f"missing {CORR}")
    d = pd.read_csv(CORR, dtype=str, keep_default_na=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    for c in (FACTOR, "Price"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Date", FACTOR, "Price"])

    # Sector 映射（corrected.csv 不含 Sector ⇒ 现场合并）
    sm = pd.read_csv(REPO / "sp500_constituents.csv", dtype=str)
    smap = {str(r["Ticker"]).strip().upper(): str(r.get("Sector") or "NA")
            for _, r in sm.iterrows()}
    d["Sector"] = d["Ticker"].astype(str).str.upper().map(smap).fillna("NA")

    prices = pd.read_csv(REPO / "research_price_history_sp500_2y.csv",
                         dtype=str, keep_default_na=False,
                         usecols=["Date", "Ticker", "Close"])
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Date", "Close"]).sort_values(["Ticker", "Date"])

    fwd = {}
    for h in HORIZONS:
        vals = []
        for tk, d0 in zip(d["Ticker"], d["Date"]):
            sub = prices[prices["Ticker"] == tk]
            if sub.empty:
                vals.append(np.nan); continue
            s = sub.set_index("Date")["Close"]
            i0 = s.index.get_indexer([d0], method="bfill")[0]
            i1 = i0 + h
            vals.append(float(s.iloc[i1] / s.iloc[i0] - 1) if i1 < len(s) else np.nan)
        fwd[f"Fwd_{h}D"] = vals
    d = d.assign(**fwd)

    # 去极值
    lo, hi = d[FACTOR].quantile(0.02), d[FACTOR].quantile(0.98)
    d = d[(d[FACTOR] >= lo) & (d[FACTOR] <= hi)].copy()

    dates = np.sort(d["Date"].unique())
    cut = dates[int(len(dates) * TRAIN_FRAC)]
    tr = d[d["Date"] < cut].copy()
    te = d[d["Date"] >= cut].copy()

    def prep(x):
        x["Pct"] = x.groupby("Sector")[FACTOR].rank(pct=True)
        x = x.dropna(subset=["Pct"])
        x["Q"] = pd.qcut(x["Pct"].rank(method="first"), Q, labels=False) + 1
        return x

    tr, te = prep(tr), prep(te)
    tr20 = stats(tr, FACTOR, +1)
    sign = +1 if (tr20[20]["ls"] or 0) >= 0 else -1
    trs, tes = stats(tr, FACTOR, sign), stats(te, FACTOR, sign)

    L = ["# BP 因子 OOS 验证（时间序列 70/30 切分）\n",
         f"> 生成脚本：`tools/research/factor_oos_validation.py`",
         f"> 因子：**`{FACTOR}`（账面市值比，行业中性化排序）**；方向由训练集决定：**{'做多高 BP' if sign > 0 else '做多低 BP'}**",
         f"> 切分点（按 Release_Proxy）：**{pd.Timestamp(cut).date()}**",
         f"> 训练集 **{len(tr)}** 观测 / 测试集 **{len(te)}** 观测\n",
         "## 1. 训练集 vs 测试集\n",
         "| 段 | 期限 | 多空(%) | t | Spearman IC | n |",
         "|---|---|---|---|---|---|"]
    for name, st in (("训练集（70%）", trs), ("测试集（30%）", tes)):
        for h in HORIZONS:
            m = st[h]
            L.append(f"| {name} | {h}D | **{m['ls']:+.3f}** | **{m['t']:+.2f}** | "
                     f"{m['ic']:+.4f} | {m['n']} |")
    L.append("")

    a, b = trs[20], tes[20]
    decay_ls = (b["ls"] - a["ls"])
    decay_ic = (b["ic"] - a["ic"])
    L += ["## 2. 结论\n",
          f"- 训练集 20D：多空 **{a['ls']:+.3f}%**，t={a['t']:+.2f}，IC={a['ic']:+.4f}（n={a['n']}）",
          f"- 测试集 20D：多空 **{b['ls']:+.3f}%**，t={b['t']:+.2f}，IC={b['ic']:+.4f}（n={b['n']}）",
          f"- **多空变化**：{decay_ls:+.3f} pp（相对衰减 "
          f"{(decay_ls / a['ls'] * 100 if a['ls'] else float('nan')):+.1f}%）",
          f"- **IC 变化**：{decay_ic:+.4f}",
          ""]
    if b["ls"] > 0 and b["t"] is not None and not np.isnan(b["t"]) and b["t"] > 0:
        L.append(f"- ✅ **样本外方向未被推翻**（测试集多空为正、t={b['t']:+.2f}）")
    else:
        L.append(f"- ✗ **样本外方向被推翻或失效**（测试集多空 {b['ls']:+.3f}%，t={b['t']:+.2f}）")
    if abs(b["ic"]) < abs(a["ic"]):
        L.append(f"- ○ **IC 出现衰减**（|IC| {abs(a['ic']):.4f} → {abs(b['ic']):.4f}）")
    L += ["", "### ⚠️ 限制\n",
          "1. 测试集观测数少（n≈30% 样本），t 值置信度低。",
          "2. 方向由**训练集**决定 ⇒ 相比 V2 已消除「同段拟合」偏差，但仍属**单次切分**（未做滚动）。",
          "3. 未扣交易成本；未做多重检验校正。", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  train n={len(tr)} test n={len(te)} cut={pd.Timestamp(cut).date()} sign={sign:+d}")
    for name, st in (("train", trs), ("test", tes)):
        m = st[20]
        print(f"  {name} 20D: ls={m['ls']:+.3f}% t={m['t']:+.2f} ic={m['ic']:+.4f} n={m['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
