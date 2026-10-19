#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BP 因子：行业构成诊断 + Walk-Forward 滚动验证（训练6月/测试3月）。

输出 docs/FACTOR_WALK_FORWARD_VALIDATION.md
判据：窗口数 N；方向一致窗口 > 2/3 且 ICIR > 0.3 ⇒ 初步稳健。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
CORR = REPO / "research_fundamentals_pit_corrected.csv"
PRICE = REPO / "research_price_history_sp500_2y.csv"
CONST = REPO / "sp500_constituents.csv"
OUT = REPO / "docs" / "FACTOR_WALK_FORWARD_VALIDATION.md"

FACTOR = "BP"
Q = 5
TRAIN_M, TEST_M, STEP_M = 6, 3, 3
H = 20


def load() -> pd.DataFrame:
    d = pd.read_csv(CORR, dtype=str, keep_default_na=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    for c in (FACTOR, "Price"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Date", FACTOR, "Price"])
    sm = pd.read_csv(CONST, dtype=str)
    smap = {str(r["Ticker"]).strip().upper(): str(r.get("Sector") or "NA")
            for _, r in sm.iterrows()}
    d["Sector"] = d["Ticker"].astype(str).str.upper().map(smap).fillna("NA")

    p = pd.read_csv(PRICE, dtype=str, keep_default_na=False,
                    usecols=["Date", "Ticker", "Close"])
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce")
    p["Close"] = pd.to_numeric(p["Close"], errors="coerce")
    p = p.dropna(subset=["Date", "Close"]).sort_values(["Ticker", "Date"])

    col = f"Fwd_{H}D"
    vals = []
    for tk, d0 in zip(d["Ticker"], d["Date"]):
        sub = p[p["Ticker"] == tk]
        if sub.empty:
            vals.append(np.nan); continue
        s = sub.set_index("Date")["Close"]
        i0 = s.index.get_indexer([d0], method="bfill")[0]
        i1 = i0 + H
        vals.append(float(s.iloc[i1] / s.iloc[i0] - 1) if i1 < len(s) else np.nan)
    d[col] = vals
    return d.dropna(subset=[col])


def prep(x: pd.DataFrame) -> pd.DataFrame:
    x = x.copy()
    x["Pct"] = x.groupby("Sector")[FACTOR].rank(pct=True)
    x = x.dropna(subset=["Pct"])
    x["Q"] = pd.qcut(x["Pct"].rank(method="first"), Q, labels=False) + 1
    return x


def window_stats(x: pd.DataFrame, sign: int):
    hi, lo = (Q, 1) if sign > 0 else (1, Q)
    col = f"Fwd_{H}D"
    a = x[x["Q"] == hi][col].dropna()
    b = x[x["Q"] == lo][col].dropna()
    if len(a) < 5 or len(b) < 5:
        return None
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    t = (a.mean() - b.mean()) / se if se > 0 else np.nan
    ic = x[[FACTOR, col]].corr(method="spearman").iloc[0, 1]
    return dict(ls=(a.mean() - b.mean()) * 100, t=t, ic=ic, n=len(x))


def main() -> int:
    d = load()
    lo_v, hi_v = d[FACTOR].quantile(0.02), d[FACTOR].quantile(0.98)
    d = d[(d[FACTOR] >= lo_v) & (d[FACTOR] <= hi_v)].copy()
    dmin, dmax = d["Date"].min(), d["Date"].max()
    print(f"rows={len(d)} range={dmin.date()}..{dmax.date()}")

    cut = pd.Timestamp("2026-06-29")
    tr, te = d[d["Date"] < cut], d[d["Date"] >= cut]

    # ---------- 行业构成诊断 ----------
    tr_c = (tr["Sector"].value_counts(normalize=True) * 100).round(1)
    te_c = (te["Sector"].value_counts(normalize=True) * 100).round(1)
    comp = pd.DataFrame({"train_pct": tr_c, "test_pct": te_c}).fillna(0.0)
    comp["diff"] = (comp["test_pct"] - comp["train_pct"]).round(1)
    comp = comp.sort_values("test_pct", ascending=False)
    top_test = comp["test_pct"].max()
    conc = top_test > 30.0
    print(f"  top test sector = {comp.index[0]} {top_test:.1f}% ⇒ 集中={conc}")

    ext = pd.concat([tr.assign(seg="train"), te.assign(seg="test")])
    q_ext = ext[(ext[FACTOR] >= ext[FACTOR].quantile(0.95))]
    ext_sector = (q_ext.groupby("seg")["Sector"].value_counts(normalize=True) * 100).round(1)

    # ---------- Walk-Forward ----------
    wins = []
    start = dmin.to_period("M")
    end = dmax.to_period("M")
    cur = start
    while True:
        tr_lo = cur
        tr_hi = cur + TRAIN_M
        te_hi = tr_hi + TEST_M
        if pd.Period(te_hi, "M").start_time > end.start_time + pd.offsets.MonthEnd(0):
            pass
        tr_mask = (d["Date"] >= tr_lo.start_time) & (d["Date"] < tr_hi.start_time)
        te_mask = (d["Date"] >= tr_hi.start_time) & (d["Date"] < te_hi.start_time)
        if te_mask.sum() >= 60 and tr_mask.sum() >= 60:
            a = prep(d[tr_mask]); b = prep(d[te_mask])
            if len(a) >= 60 and len(b) >= 60:
                s0 = window_stats(a, +1)
                if s0:
                    sign = +1 if s0["ls"] >= 0 else -1
                    sb = window_stats(b, sign)
                    if sb:
                        wins.append(dict(train=f"{tr_lo}~{tr_hi}", test=f"{tr_hi}~{te_hi}",
                                         sign=sign, tr_ls=s0["ls"], tr_t=s0["t"],
                                         ls=sb["ls"], t=sb["t"], ic=sb["ic"], n=sb["n"]))
        cur = cur + STEP_M
        if cur + TRAIN_M + TEST_M > end + 1:
            break

    L = ["# BP 因子 Walk-Forward 滚动验证 + 测试段构成诊断\n",
         "> 脚本：`tools/research/factor_walk_forward.py`",
         f"> 数据：`{CORR.name}`；因子 **`BP`**（行业中性化排序）；前瞻 **{H}D**",
         f"> 样本：**{len(d)}** 观测，{dmin.date()} ~ {dmax.date()}",
         f"> 窗口：训练 **{TRAIN_M}** 月 / 测试 **{TEST_M}** 月 / 步长 **{STEP_M}** 月；"
         f"**实际可用窗口 {len(wins)} 个**（受样本跨度限制，未达 12 个）\n",
         "## 1. 行业构成诊断（训练 vs 测试，%）\n",
         "| Sector | 训练段 | 测试段 | 差值 |", "|---|---|---|---|"]
    for sec, r in comp.head(12).iterrows():
        L.append(f"| {sec} | {r['train_pct']:.1f} | {r['test_pct']:.1f} | {r['diff']:+.1f} |")
    L.append("")
    L.append(f"**测试段最大 Sector：`{comp.index[0]}` 占 **{top_test:.1f}%** ⇒ "
             f"{'⚠️ 存在行业集中（>30%）' if conc else '未见行业集中（≤30%）'}**\n")
    L.append("### BP 极端值（P95 以上）的行业分布（%）\n")
    L.append("| 段 | Sector | 占比 |", "|---|---|---|")
    for (seg, sec), v in ext_sector.items():
        L.append(f"| {seg} | {sec} | {v:.1f} |")
    L.append("")

    L += ["## 2. Walk-Forward 结果\n",
          "| # | 训练段 | 测试段 | 方向 | 训练多空(%) | 训练t | 测试多空(%) | 测试t | IC | n |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, w in enumerate(wins, 1):
        L.append("| {} | {} | {} | {} | {:+.3f} | {:+.2f} | {:+.3f} | {:+.2f} | {:+.4f} | {} |".format(
            i, w["train"], w["test"], "多高BP" if w["sign"] > 0 else "多低BP",
            w["tr_ls"], w["tr_t"], w["ls"], w["t"], w["ic"], w["n"]))
    L.append("")

    if wins:
        ls_arr = np.array([w["ls"] for w in wins])
        ic_arr = np.array([w["ic"] for w in wins if pd.notna(w["ic"])])
        pos = int((ls_arr > 0).sum())
        icir = (ic_arr.mean() / ic_arr.std(ddof=1)) if len(ic_arr) > 1 and ic_arr.std(ddof=1) > 0 else np.nan
        robust = (pos > 2 * len(wins) / 3) and pd.notna(icir) and icir > 0.3
        L += ["## 3. 汇总\n",
              f"- 窗口数：**{len(wins)}**",
              f"- 多空为正的窗口：**{pos}/{len(wins)}**（{pos/len(wins):.0%}）",
              f"- 平均多空：**{ls_arr.mean():+.3f}%**（中位 {np.median(ls_arr):+.3f}%）",
              f"- 多空标准差：**{ls_arr.std(ddof=1):.3f}%**",
              f"- IC 均值：**{ic_arr.mean():+.4f}**，IC 标准差：**{ic_arr.std(ddof=1):.4f}**",
              f"- **ICIR = {icir:.3f}**",
              "",
              f"### 判定：**{'✅ 初步稳健' if robust else '✗ 不稳定'}**",
              f"- 判据：方向一致窗口 > 2/3（需 >{2*len(wins)/3:.1f}）且 ICIR > 0.3",
              f"- 实际：{pos}/{len(wins)} 窗口为正、ICIR={icir:.3f}",
              ""]
    else:
        L.append("## 3. 汇总\n\n- ✗ **可用窗口为 0**（样本跨度不足）\n")

    L += ["## 4. 限制\n",
          "1. 样本仅 ~16 个月 ⇒ **实际窗口数远少于 12**，统计效力有限。",
          "2. 每窗口测试集观测数小（~60-150）⇒ t/IC 噪声大。",
          "3. 未扣成本；未做多重检验校正。", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  windows={len(wins)}")
    for i, w in enumerate(wins, 1):
        print(f"  W{i} {w['test']}: ls={w['ls']:+.3f}% t={w['t']:+.2f} ic={w['ic']:+.4f} n={w['n']}")
    if wins:
        print(f"  pos={pos}/{len(wins)} mean_ls={ls_arr.mean():+.3f}% icir={icir:.3f} robust={robust}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
