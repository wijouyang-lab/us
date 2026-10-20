#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""死亡解剖：换手率与成本 / IC 衰减 / BP 归因（只读）。

三部分：
  ① 换手率与成本（行业轮动策略）—— 全量可算 ✓
  ② IC 衰减曲线 —— **仅 5/10/20D 三档可用**（数据无逐日前瞻）✗，如实标注
  ③ BP 归因回归（控制 Size 与 Sector）—— 用 Price 作 size 代理 ✗（无市值字段）

输出 docs/DEATH_AUTOPSY.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
BT = REPO / "research_backtest_sp500_pit_2y.csv"
FUND = REPO / "research_fundamentals_pit_corrected.csv"
CONST = REPO / "sp500_constituents.csv"
OUT = REPO / "docs" / "DEATH_AUTOPSY.md"

TOP_N = 3
MOM = "Momentum_20D_Pct"
COST_ONE_WAY = 0.0005      # 万分之五
HOLD = 20


def sector_map():
    if not CONST.exists():
        return {}
    sm = pd.read_csv(CONST, dtype=str)
    return {str(r["Ticker"]).strip().upper(): str(r.get("Sector") or "NA")
            for _, r in sm.iterrows()}


def part1_turnover(d: pd.DataFrame) -> dict:
    """每日按 Sector 内 Momentum 均值取最强 3 行业，计算行业层面的换手率。"""
    sets = []
    for dt, day in d.groupby("Scan_Date"):
        g = day.groupby("Sector")[MOM].mean().sort_values(ascending=False)
        if len(g) < TOP_N * 2:
            continue
        sets.append((dt, set(g.index[:TOP_N])))
    if len(sets) < 3:
        return {}
    turnovers = []
    for (_, prev), (_, cur) in zip(sets[:-1], sets[1:]):
        # 换掉的行业数 / 持仓数 ⇒ 单边换手
        churn = len(prev - cur) / max(len(prev), 1)
        turnovers.append(churn)
    t = pd.Series(turnovers)
    avg = float(t.mean())
    # 每 20 个交易日累计换手（近似：avg × 20，双边计）
    cum_single = avg * HOLD
    cum_double = cum_single * 2
    cost = cum_double * COST_ONE_WAY * 100        # %
    return dict(days=int(len(t)), avg_daily_single=avg * 100,
                avg_daily_double=avg * 2 * 100,
                cum20_single=cum_single * 100, cum20_double=cum_double * 100,
                cost20_pct=cost, changes=int((t > 0).sum()))


def part2_ic_decay() -> dict:
    """仅 5/10/20D 三档（数据限制）。"""
    return dict(note="仅 5/10/20D")


def part3_attribution(d: pd.DataFrame, smap: dict) -> dict:
    """BP ~ 20D 前瞻收益，控制 Sector 哑变量与 log(Price)（size 代理）。"""
    if not FUND.exists():
        return {}
    f = pd.read_csv(FUND, dtype=str, keep_default_na=False)
    for c in ("BP", "Price"):
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["Date"] = pd.to_datetime(f["Date"], errors="coerce")
    f = f.dropna(subset=["BP", "Date"]).rename(columns={"Date": "Scan_Date"})
    dd = d.copy()
    dd["Scan_Date"] = pd.to_datetime(dd["Scan_Date"], errors="coerce")
    dd[f"R{HOLD}"] = pd.to_numeric(dd[f"Forward_Return_{HOLD}D"], errors="coerce")
    dd = dd.dropna(subset=[f"R{HOLD}"])

    merged = []
    for tk, g in dd.groupby("Ticker"):
        fg = f[f["Ticker"] == tk].sort_values("Scan_Date")
        if fg.empty:
            continue
        m = pd.merge_asof(g.sort_values("Scan_Date"), fg[["Scan_Date", "BP"]],
                          on="Scan_Date", direction="backward")
        merged.append(m)
    if not merged:
        return {}
    m = pd.concat(merged).dropna(subset=["BP", f"R{HOLD}"])
    m["logP"] = np.log(m["Price"].astype(float).clip(lower=1e-6))
    m["Sector"] = m["Ticker"].astype(str).str.upper().map(smap).fillna("NA")

    y = m[f"R{HOLD}"].to_numpy(float)
    Xb = m[["BP"]].to_numpy(float)
    Xs = m[["logP"]].to_numpy(float)
    dum = pd.get_dummies(m["Sector"], drop_first=True).to_numpy(float)

    def ols(X, y):
        A = np.column_stack([np.ones(len(X)), X])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ beta
        n, k = A.shape
        s2 = (resid @ resid) / max(n - k, 1)
        try:
            cov = s2 * np.linalg.inv(A.T @ A)
        except np.linalg.LinAlgError:
            return None
        se = np.sqrt(np.diag(cov))
        t = beta / np.where(se == 0, np.nan, se)
        r2 = 1 - (resid @ resid) / max(float(((y - y.mean()) ** 2).sum()), 1e-12)
        return dict(beta=beta, t=t, r2=r2, n=n, k=k)

    r1 = ols(Xb, y)
    r2_ = ols(np.column_stack([Xb, Xs]), y)
    r3 = ols(np.column_stack([Xb, Xs, dum]), y)
    out = {"n": len(m)}
    for name, r in (("BP_only", r1), ("BP+size", r2_), ("BP+size+sector", r3)):
        if r:
            out[name] = dict(coef=float(r["beta"][1]), t=float(r["t"][1]), r2=float(r["r2"]))
    return out


def main() -> int:
    if not BT.exists():
        raise SystemExit(f"missing {BT}")
    d = pd.read_csv(BT, dtype=str, keep_default_na=False)
    d[MOM] = pd.to_numeric(d[MOM], errors="coerce")
    d["Sector"] = d["Ticker"].astype(str).str.upper().map(sector_map()).fillna("NA")
    d = d.dropna(subset=[MOM])
    print(f"rows={len(d)} dates={d['Scan_Date'].nunique()} sectors={d['Sector'].nunique()}")

    t1 = part1_turnover(d)
    t3 = part3_attribution(d, sector_map())
    print("part1:", t1)
    print("part3:", t3)

    # 行业轮动 20D 多空（复用此前结论 +0.1701%）
    gross = 0.1701
    cost = t1.get("cost20_pct", float("nan"))
    net = gross - cost

    L = ["# 死亡解剖：换手率 / IC 衰减 / 归因\n",
         "> 脚本：`tools/research/turnover_and_cost_analysis.py`（只读）\n",
         "## 1. 换手率与成本（行业轮动：每日重选最强 3 行业）\n",
         "| 指标 | 值 |", "|---|---|",
         f"| 样本交易日 | {t1.get('days', 0)} |",
         f"| **行业发生变化的日数** | **{t1.get('changes', 0)}** |",
         f"| **日均单边换手** | **{t1.get('avg_daily_single', float('nan')):.2f}%** |",
         f"| **日均双边换手** | **{t1.get('avg_daily_double', float('nan')):.2f}%** |",
         f"| **20D 累计单边换手** | **{t1.get('cum20_single', float('nan')):.1f}%** |",
         f"| **20D 累计双边换手** | **{t1.get('cum20_double', float('nan')):.1f}%** |",
         f"| **20D 累计交易成本**（双边 0.05%/次）| **{t1.get('cost20_pct', float('nan')):.3f}%** |",
         "",
         "### 扣除成本后的净值\n",
         f"- 行业轮动 20D 多空超额（**毛**）＝ **{gross:+.4f}%**",
         f"- 20D 累计成本 ＝ **{cost:.3f}%**",
         f"- **⇒ 净超额 ＝ {net:+.3f}%**" + (" ✗ **直接变负**" if net < 0 else " ✓ 仍为正"),
         "",
         "## 2. IC 衰减（数据受限）\n",
         "⚠️ **无法生成完整的 T+1~T+20 连续衰减曲线** ✗：",
         "`research_backtest_sp500_pit_2y.csv` 只提供 **5D / 10D / 20D** 三档前瞻收益，",
         "**没有逐日前瞻列** ⇒ 只能给出三点，无法定位【第几天衰减到 0】 ✗。",
         "",
         "| 期限 | BP 的 IC | Momentum 的 IC |",
         "|---|---|---|",
         ]
    for h in (5, 10, 20):
        col = f"Forward_Return_{h}D"
        d[col] = pd.to_numeric(d[col], errors="coerce")
        b = d[[col]].copy()
        b["MOM"] = d[MOM].values
        ic_mom = b.dropna().corr(method="spearman").iloc[0, 1] if len(b.dropna()) > 10 else np.nan
        L.append(f"| {h}D | N/A（需 BP）| {ic_mom:+.4f}（n={len(b.dropna())}）|")
    L += ["", "> 结论：**仅知 5/10/20D 三点 ⇒ 无法判定【3 天衰减】假设** ✗ —— 需补逐日前瞻数据 ✓",
          "",
          "## 3. BP 归因回归（控制 Size 与 Sector）\n"]
    if t3:
        L += [f"> 样本 **{t3['n']:,}** 行；Size 用 `log(Price)` **代理**（无市值字段 ✗）\n",
              "| 模型 | BP 系数 | **BP 的 t 值** | R² |", "|---|---|---|---|",
              f"| 仅 BP | {t3['BP_only']['coef']:.6f} | **{t3['BP_only']['t']:+.2f}** | {t3['BP_only']['r2']:.5f} |"]
        if "BP+size" in t3:
            L.append(f"| BP + Size | {t3['BP+size']['coef']:.6f} | **{t3['BP+size']['t']:+.2f}** | {t3['BP+size']['r2']:.5f} |")
        if "BP+size+sector" in t3:
            L.append(f"| BP + Size + Sector 哑变量 | {t3['BP+sector']['coef'] if 'BP+sector' in t3 else t3['BP+size+sector']['coef']:.6f} | "
                     f"**{t3['BP+size+sector']['t']:+.2f}** | {t3['BP+size+sector']['r2']:.5f} |")
        L += ["", "### 判读\n"]
        t_final = t3.get("BP+size+sector", {}).get("t", np.nan)
        t_only = t3.get("BP_only", {}).get("t", np.nan)
        L.append(f"- 仅 BP：t = **{t_only:+.2f}**")
        L.append(f"- 控制 Size + Sector 后：t = **{t_final:+.2f}**")
        if pd.notna(t_final) and abs(t_final) < 1.96:
            L.append(f"- **⇒ 控制风格后 BP 不再显著（|t| < 1.96）⇒ BP 的收益来自 Size/行业风格，不是 BP 本身** ✗✓")
        else:
            L.append(f"- **⇒ 控制风格后 BP 仍显著（|t| ≥ 1.96）⇒ BP 有独立解释力** ✓")
    else:
        L.append("❌ 无法完成归因（缺 BP 或价格数据） ✗")
    L += ["", "## 4. ⚠️ 限制\n",
          "1. **无市值字段** ⇒ Size 用 `log(Price)` 代理，**不等价** ✗",
          "2. **Sector 用当前映射** ⇒ PIT 行业漂移不可复现 ✗",
          "3. **换手率按【行业层面】计算**（买入整个行业）⇒ 真实个股换手更高 ✗",
          "4. IC 衰减**只有 3 个点** ✗",
          ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  gross={gross:+.4f}%  cost={cost:.3f}%  net={net:+.3f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
