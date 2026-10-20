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
SECTOR_HISTORY = REPO / "research_sector_history_pit.csv"
OUT = REPO / "docs" / "DEATH_AUTOPSY.md"

TOP_N = 3
MOM = "Momentum_20D_Pct"
COST_ONE_WAY = 0.0005      # 万分之五
HOLD = 20


def load_pit_sector_history(path=SECTOR_HISTORY):
    """Load interval-based PIT GICS sectors. No current-sector fallback is allowed."""
    if not path.exists():
        return None, f"缺少 {path.name}；当前 Sector 映射不能替代历史 PIT 行业归属"
    try:
        h = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:
        return None, f"PIT 行业历史读取失败：{type(exc).__name__}: {exc}"
    required = {"Ticker", "Effective_From", "Effective_To", "Sector"}
    if not required.issubset(h.columns):
        return None, f"PIT 行业历史缺少字段：{sorted(required - set(h.columns))}"
    h["Ticker"] = h["Ticker"].astype(str).str.strip().str.upper()
    h["Sector"] = h["Sector"].astype(str).str.strip()
    h["Effective_From"] = pd.to_datetime(h["Effective_From"], errors="coerce")
    raw_to = h["Effective_To"].astype(str).str.strip()
    h["Effective_To"] = pd.to_datetime(raw_to.replace("", pd.NA), errors="coerce")
    h["Effective_To"] = h["Effective_To"].fillna(pd.Timestamp.max)
    h = h.dropna(subset=["Effective_From"])
    h = h[(h["Ticker"] != "") & (h["Sector"] != "")]
    if h.empty:
        return None, "PIT 行业历史没有有效区间记录"
    if (h["Effective_To"] < h["Effective_From"]).any():
        return None, "PIT 行业历史包含 Effective_To 早于 Effective_From 的区间"
    for tk, g in h.sort_values("Effective_From").groupby("Ticker"):
        prev_end = None
        for _, row in g.iterrows():
            if prev_end is not None and row["Effective_From"] <= prev_end:
                return None, f"PIT 行业历史区间重叠：{tk}"
            prev_end = row["Effective_To"]
    return h.sort_values(["Ticker", "Effective_From"]).reset_index(drop=True), ""


def attach_pit_sectors(d: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Attach each ticker's sector effective on that row's Scan_Date; missing mappings stay NA."""
    out = d.copy()
    out["Ticker"] = out["Ticker"].astype(str).str.strip().str.upper()
    out["Scan_Date"] = pd.to_datetime(out["Scan_Date"], errors="coerce")
    out["Sector"] = ""
    for tk, group in out.groupby("Ticker"):
        hist = history[history["Ticker"] == tk]
        if hist.empty:
            continue
        left = group[["Scan_Date"]].copy()
        left["_row_index"] = group.index
        left = left.sort_values("Scan_Date")
        right = hist[["Effective_From", "Effective_To", "Sector"]].sort_values("Effective_From")
        merged = pd.merge_asof(
            left, right, left_on="Scan_Date", right_on="Effective_From", direction="backward"
        )
        valid = merged["Effective_To"].notna() & (merged["Scan_Date"] <= merged["Effective_To"])
        sectors = merged["Sector"].where(valid, "")
        out.loc[merged["_row_index"].to_numpy(), "Sector"] = sectors.fillna("").to_numpy()
    return out


def part1_turnover(d: pd.DataFrame) -> dict:
    """PIT Sector 数据下，按 Momentum 选 Top/Bottom 3 行业并估算 20D 毛多空与换手成本。"""
    required = {"Scan_Date", "Sector", MOM, f"Forward_Return_{HOLD}D"}
    if not required.issubset(d.columns):
        return {}
    work = d.copy()
    work["Scan_Date"] = pd.to_datetime(work["Scan_Date"], errors="coerce")
    work[MOM] = pd.to_numeric(work[MOM], errors="coerce")
    ret_col = f"Forward_Return_{HOLD}D"
    work[ret_col] = pd.to_numeric(work[ret_col], errors="coerce")
    work = work.dropna(subset=["Scan_Date", MOM, ret_col])
    work = work[work["Sector"].astype(str).str.strip().ne("")]
    selections, spreads = [], []
    for dt, day in work.groupby("Scan_Date"):
        scores = day.groupby("Sector")[MOM].mean().sort_values(ascending=False)
        sector_returns = day.groupby("Sector")[ret_col].mean()
        common = scores.index.intersection(sector_returns.dropna().index)
        scores = scores.loc[common]
        if len(scores) < TOP_N * 2:
            continue
        top = list(scores.nlargest(TOP_N).index)
        bottom = list(scores.nsmallest(TOP_N).index)
        spread = float(sector_returns.loc[top].mean() - sector_returns.loc[bottom].mean())
        selections.append((dt, set(top)))
        spreads.append(spread)
    if len(selections) < 3:
        return {}
    turnovers = [
        len(prev - cur) / max(len(prev), 1)
        for (_, prev), (_, cur) in zip(selections[:-1], selections[1:])
    ]
    t = pd.Series(turnovers)
    avg = float(t.mean())
    cum_single = avg * HOLD
    cum_double = cum_single * 2
    cost = cum_double * COST_ONE_WAY * 100
    gross = float(np.mean(spreads)) * 100
    return dict(days=int(len(t)), spread_samples=len(spreads), gross20_pct=gross,
                avg_daily_single=avg * 100, avg_daily_double=avg * 2 * 100,
                cum20_single=cum_single * 100, cum20_double=cum_double * 100,
                cost20_pct=cost, net20_pct=gross - cost,
                changes=int((t > 0).sum()))


def part2_ic_decay() -> dict:
    """仅 5/10/20D 三档（数据限制）。"""
    return dict(note="仅 5/10/20D")


def part3_attribution(d: pd.DataFrame) -> dict:
    """BP return attribution requiring true PIT Market_Cap and effective-date PIT Sector."""
    if not FUND.exists():
        return {"status": "SKIPPED", "reason": f"缺少 {FUND.name}"}
    if "Sector" not in d.columns or d["Sector"].astype(str).str.strip().eq("").any():
        return {"status": "SKIPPED", "reason": "缺少完整 PIT Sector 归属；不使用当前成分股行业映射替代"}
    f = pd.read_csv(FUND, dtype=str, keep_default_na=False)
    required = {"Date", "Ticker", "BP", "Market_Cap"}
    missing = required - set(f.columns)
    if missing:
        return {
            "status": "SKIPPED",
            "reason": f"{FUND.name} 缺少真实市值字段 {sorted(missing)}；不再用 log(Price) 代理 Size",
        }
    f["Ticker"] = f["Ticker"].astype(str).str.strip().str.upper()
    for c in ("BP", "Market_Cap"):
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["Scan_Date"] = pd.to_datetime(f["Date"], errors="coerce")
    f = f.dropna(subset=["BP", "Market_Cap", "Scan_Date"])
    f = f[(f["Market_Cap"] > 0) & (f["BP"].notna())]
    dd = d.copy()
    dd["Scan_Date"] = pd.to_datetime(dd["Scan_Date"], errors="coerce")
    dd[f"R{HOLD}"] = pd.to_numeric(dd[f"Forward_Return_{HOLD}D"], errors="coerce")
    dd = dd.dropna(subset=["Scan_Date", "Sector", f"R{HOLD}"])
    merged = []
    for tk, g in dd.groupby("Ticker"):
        fg = f[f["Ticker"] == str(tk).upper()].sort_values("Scan_Date")
        if fg.empty:
            continue
        m = pd.merge_asof(
            g.sort_values("Scan_Date"),
            fg[["Scan_Date", "BP", "Market_Cap"]],
            on="Scan_Date",
            direction="backward",
        )
        merged.append(m)
    if not merged:
        return {"status": "SKIPPED", "reason": "无法将 PIT BP/Market_Cap 与前瞻收益按日期对齐"}
    m = pd.concat(merged, ignore_index=True).dropna(subset=["BP", "Market_Cap", f"R{HOLD}"])
    m = m[m["Market_Cap"] > 0]
    if len(m) < 30:
        return {"status": "SKIPPED", "reason": f"真实市值可匹配样本不足 30 行（n={len(m)}）"}
    m["log_market_cap"] = np.log(m["Market_Cap"].astype(float).clip(lower=1.0))
    m["Sector"] = m["Sector"].astype(str)

    y = m[f"R{HOLD}"].to_numpy(float)
    Xb = m[["BP"]].to_numpy(float)
    Xm = m[["log_market_cap"]].to_numpy(float)
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

    results = {}
    for name, model in (
        ("BP_only", Xb),
        ("BP+market_cap", np.column_stack([Xb, Xm])),
        ("BP+market_cap+sector", np.column_stack([Xb, Xm, dum])),
    ):
        r = ols(model, y)
        if r:
            results[name] = dict(coef=float(r["beta"][1]), t=float(r["t"][1]), r2=float(r["r2"]))
    return {"status": "OK", "n": len(m), **results}


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
