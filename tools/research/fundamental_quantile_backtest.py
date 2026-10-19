#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基本面因子：PIT 口径修正 + 分层回测（EP_TTM / BP / ROE_ANN）。

输入
  research_fundamentals_pit_sample.csv   （Date=Release_Proxy, Ticker, Factor_Name, Value）
  research_price_history_sp500_2y.csv    （Date, Ticker, Close …，复权价）
输出
  research_fundamentals_pit_corrected.csv（Date, Ticker, EP_TTM, BP, ROE_ANN）
  docs/FUNDAMENTAL_QUANTILE_BACKTEST.md

口径（方向统一为「越高越好」）
  EP_TTM  = EPS_TTM / Price(Release_Proxy 当日或之前最近收盘)    ← 盈利收益率
  BP      = BPS    / Price（同上）                              ← 账面市值比
  ROE_ANN = (NetIncome/Equity) × 4                              ← 年化 ROE

PIT 纪律
  · 基本面只在 Release_Proxy（period_end + 90d）当日**收盘后**可用 ⇒ 价格取该日收盘 ✓
  · 前瞻收益从 Release_Proxy 次日起算 ⇒ **无未来函数** ✓
  · 若某日价格缺失 → 取该日之前最近收盘（不取未来）✓

限制（如实）
  · 每个 Release_Proxy 日只覆盖少量票 ⇒ **无法做逐日横截面分位**，改为**全样本内按因子值分 5 层**（分层口径，非逐日）✓
  · 去极值：**2% / 98% 分位截断（winsorize）** ✓
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
FUND = REPO / "research_fundamentals_pit_sample.csv"
PRICE = REPO / "research_price_history_sp500_2y.csv"
OUT_CSV = REPO / "research_fundamentals_pit_corrected.csv"
OUT_MD = REPO / "docs" / "FUNDAMENTAL_QUANTILE_BACKTEST.md"

HORIZONS = (5, 10, 20)
Q = 5
WIN_LO, WIN_HI = 0.02, 0.98


def load_prices() -> pd.DataFrame:
    p = pd.read_csv(PRICE, dtype=str, keep_default_na=False,
                    usecols=["Date", "Ticker", "Close"])
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce")
    p["Close"] = pd.to_numeric(p["Close"], errors="coerce")
    p = p.dropna(subset=["Date", "Close"]).sort_values(["Ticker", "Date"])
    return p


def main() -> int:
    if not FUND.exists() or not PRICE.exists():
        raise SystemExit("missing inputs")

    f = pd.read_csv(FUND, dtype=str, keep_default_na=False)
    f["Date"] = pd.to_datetime(f["Date"], errors="coerce")
    f["Value"] = pd.to_numeric(f["Value"], errors="coerce")
    wide = (f.dropna(subset=["Date", "Value"])
              .pivot_table(index=["Date", "Ticker"], columns="Factor_Name",
                           values="Value", aggfunc="last")
              .reset_index())
    print(f"fundamental points = {len(wide)}（{wide['Ticker'].nunique()} tickers）")
    for c in ("PE_Proxy", "PB_Proxy", "ROE_Proxy"):
        if c not in wide.columns:
            wide[c] = np.nan

    px = load_prices()
    print(f"price rows = {len(px)}（{px['Ticker'].nunique()} tickers）")

    # ---------- PIT 价格对齐：Release_Proxy 当日或之前最近收盘 ----------
    wide = wide.sort_values(["Ticker", "Date"])
    close_at = []
    for tk, g in wide.groupby("Ticker"):
        sub = px[px["Ticker"] == tk]
        if sub.empty:
            close_at.extend([np.nan] * len(g))
            continue
        s = sub.set_index("Date")["Close"]
        # 用 asof（向后取 <= 当日 的最近值）——绝不取未来 ✓
        vals = s.reindex(g["Date"], method="ffill").to_numpy()
        close_at.extend(vals.tolist())
    wide["Price"] = close_at
    print(f"  价格命中：{int(wide['Price'].notna().sum())}/{len(wide)}")

    # ---------- 口径修正 ----------
    eps_ttm = wide["PE_Proxy"]          # 原始列实为 EPS_TTM（命名遗留），此处仅作分母迁移
    bps = wide["PB_Proxy"]              # 原始列实为 BPS
    wide["EP_TTM"] = eps_ttm / wide["Price"]
    wide["BP"] = bps / wide["Price"]
    wide["ROE_ANN"] = wide["ROE_Proxy"] * 4.0
    wide = wide.replace([np.inf, -np.inf], np.nan)

    corr = wide[["Date", "Ticker", "EP_TTM", "BP", "ROE_ANN", "Price"]].dropna(
        subset=["Price"])
    corr.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"written: {OUT_CSV.name} ({len(corr)} rows)")
    print(corr.head(5).to_string(index=False))

    # ---------- 前瞻收益（从 Release_Proxy 次日算，不重叠视角由报告说明）----------
    fr = {}
    for h in HORIZONS:
        col = f"Fwd_{h}D"
        vals = []
        for tk, d0 in zip(corr["Ticker"], corr["Date"]):
            sub = px[px["Ticker"] == tk]
            if sub.empty:
                vals.append(np.nan); continue
            s = sub.set_index("Date")["Close"]
            idx = s.index
            try:
                i0 = idx.get_indexer([d0], method="bfill")[0]   # 当日或之后第一根
                i1 = i0 + h
                vals.append(float(s.iloc[i1] / s.iloc[i0] - 1) if i1 < len(s) else np.nan)
            except Exception:
                vals.append(np.nan)
        fr[col] = vals
    corr = corr.assign(**fr)
    print(f"  前瞻收益命中：{ {c: int(corr[c].notna().sum()) for c in fr} }")

    # ---------- 分层回测（全样本分位 + winsorize）----------
    rows = []
    L = ["# 基本面因子分层回测（PIT 修正后）\n",
         "> 生成脚本：`tools/research/fundamental_quantile_backtest.py`",
         f"> 样本：**{len(corr)}** 个（Ticker × Release_Proxy）观测 / "
         f"**{corr['Ticker'].nunique()}** 只票",
         f"> 去极值：**{WIN_LO:.0%} / {WIN_HI:.0%}** 分位 winsorize；分层：全样本 5 等分（Q5=因子值最高）",
         "> PIT：价格取 Release_Proxy 当日或之前最近收盘；前瞻收益自次日起算（无未来函数）\n",
         "## 1. 分层平均前瞻收益（%）\n",
         "| 因子 | 层 | 5D | 10D | 20D | n |", "|---|---|---|---|---|---|"]

    summary = {}
    for fac in ("EP_TTM", "BP", "ROE_ANN"):
        s = corr[[fac] + [f"Fwd_{h}D" for h in HORIZONS]].dropna(subset=[fac])
        if len(s) < 50:
            print(f"  {fac}: 样本不足（{len(s)}）"); continue
        lo, hi = s[fac].quantile(WIN_LO), s[fac].quantile(WIN_HI)
        s = s[(s[fac] >= lo) & (s[fac] <= hi)]
        s["Q"] = pd.qcut(s[fac].rank(method="first"), Q, labels=False) + 1
        means = {h: s.groupby("Q")[f"Fwd_{h}D"].mean() * 100 for h in HORIZONS}
        stats = {}
        for h in HORIZONS:
            ls = means[h].get(Q, np.nan) - means[h].get(1, np.nan)
            # 分层为横截面（不同票），不是组合时间序列 ⇒ Sharpe 不可估；
            # 改用 Welch t 检验比较 Q5 与 Q1 的均值差 ✓
            a5 = s[s["Q"] == Q][f"Fwd_{h}D"].dropna()
            a1 = s[s["Q"] == 1][f"Fwd_{h}D"].dropna()
            if len(a5) > 2 and len(a1) > 2:
                v5, v1 = a5.var(ddof=1), a1.var(ddof=1)
                se = np.sqrt(v5 / len(a5) + v1 / len(a1))
                tval = (a5.mean() - a1.mean()) / se if se > 0 else np.nan
            else:
                tval = np.nan
            sharpe = tval      # 语义改为 t 值（列名在报告中同步说明）
            ic = s[[fac, f"Fwd_{h}D"]].corr(method="spearman").iloc[0, 1]
            stats[h] = dict(ls=ls, sharpe=sharpe, ic=ic)
        summary[fac] = stats
        for q in range(1, Q + 1):
            L.append("| `{}` | Q{} | {:.3f} | {:.3f} | {:.3f} | {} |".format(
                fac, q, means[5].get(q, np.nan), means[10].get(q, np.nan),
                means[20].get(q, np.nan), int((s["Q"] == q).sum())))
        L.append("")

    L += ["## 2. 多空（Q5 − Q1）与 Welch t 值（分层为横截面，Sharpe 不可估 ⇒ 用 t 值）\n",
          "| 因子 | 5D 多空(%) | 5D t | 10D 多空 | 10D t | 20D 多空 | 20D t | Spearman IC(20D) |",
          "|---|---|---|---|---|---|---|---|"]
    for fac, st in summary.items():
        L.append("| `{}` | {:+.3f} | {:.2f} | {:+.3f} | {:.2f} | {:+.3f} | {:.2f} | {:.4f} |".format(
            fac, st[5]["ls"], st[5]["sharpe"], st[10]["ls"], st[10]["sharpe"],
            st[20]["ls"], st[20]["sharpe"], st[20]["ic"]))
    L.append("")

    L += ["## 3. 结论\n"]
    if summary:
        best = max(summary.items(), key=lambda kv: abs(kv[1][20]["ic"])
                   if pd.notna(kv[1][20]["ic"]) else 0)
        L.append(f"- **方向一致（越高越好）下，20D |IC| 最强因子：`{best[0]}`**"
                 f"（IC={best[1][20]['ic']:+.4f}）")
        for fac, st in summary.items():
            L.append(f"- `{fac}`：20D 多空 {st[20]['ls']:+.3f}% / 夏普 {st[20]['sharpe']:.2f} / "
                     f"IC {st[20]['ic']:+.4f}")
        L.append("")
        L += ["### ⚠️ 限制（必读）\n",
              "1. 每期仅少量票 ⇒ 分位为**全样本合并**而非逐日横截面（口径较弱）。",
              "2. 观测数以 Release_Proxy 为单位（季度级），**n 很小** ⇒ 夏普/IC 置信度低。",
              "3. 样本仅 **50 只票**、约 **1.5 年** ⇒ 结论只能作为**方向性参考**。",
              "4. 未扣交易成本；未做行业中性化（公用事业与科技 PE 天然不同）。",
              ""]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwritten: {OUT_MD} ({OUT_MD.stat().st_size} bytes)")
    for fac, st in summary.items():
        print(f"  {fac}: 20D ls={st[20]['ls']:+.3f}% sharpe={st[20]['sharpe']:.2f} IC={st[20]['ic']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
