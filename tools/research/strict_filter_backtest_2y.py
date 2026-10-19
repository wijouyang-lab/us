#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2y PIT 严筛参数回测（Composite 分位等价替代 Quant_Score）。

三类偏差（报告与终端同步标注）：
  1. Gate_Status 不可复现 —— 模拟「全池严筛」而非生产「硬门槛后严筛」
  2. 重叠偏差 —— 逐日截面，20D 前瞻重叠 ~20x ⇒ 夏普被高估约 √20≈4.5 倍
  3. Composite 替代 Quant_Score —— 量纲 0-1 vs 0-100，仅分位等价，语义不同
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
SNAP = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
BT = REPO / "research_backtest_sp500_pit_2y.csv"
PRICE = REPO / "research_price_history_sp500_2y.csv"
CONST = REPO / "sp500_constituents.csv"
OUT = REPO / "docs" / "STRICT_FILTER_BACKTEST_2Y.md"

SIGN = {
    "ATR_Pct": +1, "Beta_60D_SPY": +1, "Volume_Ratio_20D": +1,
    "Momentum_5D_Pct": -1, "Momentum_20D_Pct": -1, "Momentum_60D_Pct": -1,
    "RSI": -1, "MA20_Slope_Pct_5D": -1, "乖离率(%)": -1, "ZScore_20D": -1,
    "Stock_RS_20D_vs_SPY": -1, "KDJ_J": -1, "MACD_HIST_LAST": -1, "量比": -1,
}
HORIZONS = (5, 10, 20)
STOP_PCT = 0.05
MAX_CAND = 3
COMBOS = [
    ("C1", 0.99, 2.0, "high20"),
    ("C2", 0.95, 2.0, "high20"),
    ("C3", 0.90, 2.0, "high20"),
    ("C4", 0.99, 2.0, "virtual"),
    ("C5", 0.95, 1.0, "high20"),
    ("C6", 0.90, 0.5, "high20"),
    ("C7", 0.95, 1.0, "virtual"),
]


def main() -> int:
    for p in (SNAP, BT, PRICE, CONST):
        if not p.exists():
            raise SystemExit(f"missing {p}")

    snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
    bt = pd.read_csv(BT, dtype=str, keep_default_na=False)
    key = ["Ticker", "Technical_Date"]
    keep = key + ["Scan_Date"] + [f"Forward_Return_{h}D" for h in HORIZONS] + \
           [f"Win_{h}D" for h in HORIZONS]
    keep = [c for c in keep if c in bt.columns]
    d = snap.merge(bt[keep], on=key, how="inner", suffixes=("", "_bt"))
    if "Scan_Date_bt" in d.columns:
        d["Scan_Date"] = d["Scan_Date_bt"]
    print(f"merged rows = {len(d)}")

    factors = [f for f in SIGN if f in d.columns]
    for c in factors + ["Price"] + [f"Forward_Return_{h}D" for h in HORIZONS] + \
             [f"Win_{h}D" for h in HORIZONS]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d["Scan_Date"] = pd.to_datetime(d["Scan_Date"], errors="coerce")
    d = d.dropna(subset=["Scan_Date", "Price"])

    # ---------- Composite：每日截面百分位 × 方向 ----------
    g = d.groupby("Scan_Date")
    rk = pd.DataFrame(index=d.index)
    for f in factors:
        rk[f] = g[f].rank(pct=True) * SIGN[f]
    d["Composite"] = rk[factors].mean(axis=1)
    d = d.dropna(subset=["Composite"])
    print(f"Composite ready: rows={len(d)} dates={d['Scan_Date'].nunique()} factors={len(factors)}")

    # ---------- Sector 映射 ----------
    sm = pd.read_csv(CONST, dtype=str)
    smap = {str(r["Ticker"]).strip().upper(): str(r.get("Sector") or "NA")
            for _, r in sm.iterrows()}
    d["Sector"] = d["Ticker"].astype(str).str.upper().map(smap).fillna("NA")

    # ---------- high20（仅对 Composite ≥ P90 的候选计算，省时）----------
    thr90 = d.groupby("Scan_Date")["Composite"].transform(lambda s: s.quantile(0.90))
    cand_mask = d["Composite"] >= thr90
    need = d[cand_mask].copy()
    px = pd.read_csv(PRICE, dtype=str, keep_default_na=False, usecols=["Date", "Ticker", "Close"])
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    px["Close"] = pd.to_numeric(px["Close"], errors="coerce")
    px = px.dropna(subset=["Date", "Close"]).sort_values(["Ticker", "Date"])
    by_tk = {tk: g_.set_index("Date")["Close"] for tk, g_ in px.groupby("Ticker")}
    h20 = {}
    for tk, d0 in zip(need["Ticker"], need["Scan_Date"]):
        ser = by_tk.get(tk)
        if ser is None or ser.empty:
            continue
        pos = ser.index.searchsorted(d0, side="right") - 1
        if pos < 0:
            continue
        w = ser.iloc[max(0, pos - 19):pos + 1]
        if len(w) >= 5:
            h20[(tk, d0)] = float(w.max())
    need["High20"] = [h20.get((t, dd)) for t, dd in zip(need["Ticker"], need["Scan_Date"])]
    print(f"  High20 coverage on candidates: {need['High20'].notna().sum()}/{len(need)}")

    rows, picks = [], {}
    for cid, q, min_rr, mode in COMBOS:
        sel = []
        for dt, day in need.groupby("Scan_Date"):
            thr = day["Composite"].quantile(q)
            cand = day[day["Composite"] >= thr]
            if cand.empty:                        # 该日 P99 无票 ⇒ 取 top1
                cand = day.nlargest(1, "Composite")
            used, out = set(), []
            for _, r in cand.iterrows():
                price = r["Price"]
                if pd.isna(price) or price <= 0:
                    continue
                stop = price * (1 - STOP_PCT)
                if mode == "high20":
                    tgt = r["High20"]
                    if tgt is None or pd.isna(tgt):
                        continue
                else:
                    tgt = price + 2 * (price - stop)
                rr = (tgt - price) / (price - stop)
                if pd.isna(rr) or rr < min_rr:
                    continue
                sec = (r.get("Sector") or "").strip()
                if sec and sec != "NA" and sec in used:
                    continue
                if sec:
                    used.add(sec)
                out.append(r)
            out.sort(key=lambda x: -x["Composite"])
            sel.extend(out[:MAX_CAND])
        s = pd.DataFrame(sel)
        picks[cid] = s
        st = {"n": len(s), "dates": int(s["Scan_Date"].nunique()) if len(s) else 0}
        for h in HORIZONS:
            ret = pd.to_numeric(s[f"Forward_Return_{h}D"], errors="coerce").dropna() if len(s) else pd.Series(dtype=float)
            win = pd.to_numeric(s[f"Win_{h}D"], errors="coerce").dropna() if len(s) else pd.Series(dtype=float)
            st[h] = dict(
                mean=float(ret.mean()) * 100 if len(ret) else np.nan,
                win=float(win.mean()) * 100 if len(win) else np.nan,
                n=int(len(ret)),
                sharpe=float(ret.mean() / ret.std(ddof=1) * np.sqrt(252 / h))
                if len(ret) > 2 and ret.std(ddof=1) > 0 else np.nan,
            )
        rows.append((cid, q, min_rr, mode, st))
        print(f"  {cid} q={q} rr>={min_rr} {mode}: n={st['n']} "
              f"20D win={st[20]['win'] if not pd.isna(st[20]['win']) else float('nan'):.1f}% "
              f"20D mean={st[20]['mean']:+.2f}%")

    # ---------------- 报告 ----------------
    L = ["# 2y PIT 严筛参数回测（Composite 分位等价）\n",
         "## 0. ⚠️ 偏差声明（必读）\n",
         "1. **`Gate_Status` 不可复现** —— 本次模拟「**全池严筛**」，生产是「**硬门槛后严筛**」",
         "   ⇒ 通过率与样本构成都会偏离生产。",
         "2. **重叠偏差** —— 逐日截面（~443 个 Scan_Date），20D 前瞻重叠约 20 倍",
         "   ⇒ **夏普被系统性高估约 √20 ≈ 4.5 倍**，不可当作真实年化夏普。",
         "3. **`Composite` 替代 `Quant_Score`** —— 量纲 0-1 vs 0-100；成分是 14 个技术因子等权",
         "   vs 生产 `F+E+T+R` 相加 ⇒ **仅分位等价，语义不同**。\n",
         f"> 输入：`{SNAP.name}` ∩ `{BT.name}` ⇒ **{len(d)}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date",
         f"> 止损统一 {STOP_PCT:.0%}；每日 ≤{MAX_CAND} 只；板块 ≤1 只/板块\n",
         "## 1. 7 组合统计\n",
         "| 组合 | 分位阈值 | R/R | target | 选出票数 | 5D 胜率 | 10D 胜率 | 20D 胜率 | 5D 均收益 | 10D | 20D | 20D 夏普* |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cid, q, rr, mode, st in rows:
        if st["n"] == 0:
            L.append(f"| {cid} | P{int(q*100)} | {rr} | {mode} | **0（无样本）** | — | — | — | — | — | — | — |")
            continue
        L.append("| {} | P{} | {} | {} | **{}** | {:.1f}% | {:.1f}% | {:.1f}% | {:+.2f}% | {:+.2f}% | {:+.2f}% | {:.2f} |".format(
            cid, int(q * 100), rr, mode, st["n"],
            st[5]["win"], st[10]["win"], st[20]["win"],
            st[5]["mean"], st[10]["mean"], st[20]["mean"], st[20]["sharpe"]))
    L.append("\n`*` 夏普含重叠偏差，高估约 4.5 倍。\n")

    ok = [(cid, st) for cid, _, _, _, st in rows if st["n"] > 0]
    L += ["## 2. 20D 胜率排名\n"]
    if ok:
        L += ["| 排名 | 组合 | 20D 胜率 | 票数 | 置信度 |", "|---|---|---|---|---|"]
        for i, (cid, st) in enumerate(sorted(ok, key=lambda x: -x[1][20]["win"]), 1):
            conf = "充足（≥30）" if st["n"] >= 30 else "**样本不足，置信度低**（<30）"
            L.append(f"| {i} | {cid} | {st[20]['win']:.1f}% | {st['n']} | {conf} |")
    else:
        L.append("**全部组合无样本** ✗")
    L.append("")

    L += ["## 3. 样本量警告\n"]
    low = [cid for cid, st in ok if st["n"] < 30]
    L.append("样本 < 30 的组合：" + ("、".join(low) if low else "无") + "\n")
    L += ["## 4. 结论\n"]
    if ok:
        best = max(ok, key=lambda x: x[1][20]["win"])
        L.append(f"- **20D 胜率最高：`{best[0]}`（{best[1][20]['win']:.1f}%，n={best[1]['n']}）**")
        L.append(f"- 其 20D 平均收益 {best[1][20]['mean']:+.2f}%，夏普 {best[1][20]['sharpe']:.2f}（含重叠偏差）")
        L.append(f"- **样本充足性**：{'✅ 是' if best[1]['n'] >= 30 else '✗ 否（<30）'}")
    else:
        L.append("- 无可用样本")
    L += ["", "### ⚠️ 不可忽视的三点\n",
          "1. 胜率差异若 < 5 个百分点，**在 n<100 时基本是噪声**。",
          "2. **不含 `Gate_Status`** ⇒ 生产实际候选池更小、质量更高，本次结论偏向「宽池」特征。",
          "3. 未扣成本；本报告**不能直接作为上线依据**。", ""]

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwritten: {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
