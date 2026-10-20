#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""死亡解剖：换手率与成本 / IC 衰减 / BP 归因（只读）。

三部分：
  ① 换手率与成本（行业轮动策略）—— 全量可算 ✓
  ② IC 衰减曲线 —— **仅 5/10/20D 三档可用**（数据无逐日前瞻）✗，如实标注
  ③ BP 归因回归——必须具备真实 PIT Market_Cap 与有效日期 PIT Sector；任一缺失则 fail-closed

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


def mean_daily_ic(d: pd.DataFrame, factor: str, return_col: str, min_cross_section: int = 10) -> dict:
    """Cross-sectional Spearman IC per Scan_Date, summarized across dates.

    A pooled correlation across all ticker-date rows mixes cross-sectional signal with
    time-series effects and is not the standard daily factor-IC definition.
    """
    required = {"Scan_Date", factor, return_col}
    if not required.issubset(d.columns):
        return {"status": "SKIPPED", "reason": f"缺少字段 {sorted(required - set(d.columns))}", "n_dates": 0}
    work = d[["Scan_Date", factor, return_col]].copy()
    work["Scan_Date"] = pd.to_datetime(work["Scan_Date"], errors="coerce")
    work[factor] = pd.to_numeric(work[factor], errors="coerce")
    work[return_col] = pd.to_numeric(work[return_col], errors="coerce")
    work = work.dropna(subset=["Scan_Date", factor, return_col])
    daily = []
    for date, group in work.groupby("Scan_Date"):
        if len(group) < min_cross_section:
            continue
        if group[factor].nunique() < 2 or group[return_col].nunique() < 2:
            continue
        ic = group[factor].corr(group[return_col], method="spearman")
        if pd.notna(ic) and np.isfinite(ic):
            daily.append({"date": date, "ic": float(ic), "n": len(group)})
    if not daily:
        return {
            "status": "SKIPPED",
            "reason": f"无横截面样本数 ≥ {min_cross_section} 且两变量非恒定的日期",
            "n_dates": 0,
        }
    values = pd.Series([item["ic"] for item in daily], dtype=float)
    return {
        "status": "OK",
        "mean_ic": float(values.mean()),
        "median_ic": float(values.median()),
        "positive_date_pct": float((values > 0).mean() * 100),
        "n_dates": int(len(daily)),
        "median_cross_section": float(np.median([item["n"] for item in daily])),
    }


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
    if "Scan_Date" not in d.columns or "Ticker" not in d.columns or MOM not in d.columns:
        raise SystemExit("backtest CSV 缺少 Scan_Date/Ticker/Momentum 必需字段")
    d["Scan_Date"] = pd.to_datetime(d["Scan_Date"], errors="coerce")
    d[MOM] = pd.to_numeric(d[MOM], errors="coerce")
    d["Ticker"] = d["Ticker"].astype(str).str.strip().str.upper()
    d = d.dropna(subset=["Scan_Date", MOM])
    d = d[d["Ticker"].ne("")]
    history, sector_reason = load_pit_sector_history()
    if history is None:
        d["Sector"] = ""
        sector_ready = False
        sector_coverage = 0.0
    else:
        d = attach_pit_sectors(d, history)
        sector_coverage = float(d["Sector"].astype(str).str.strip().ne("").mean()) if len(d) else 0.0
        sector_ready = sector_coverage >= 0.99
        if not sector_ready:
            sector_reason = (
                f"PIT Sector 覆盖率仅 {sector_coverage:.2%}，低于 99% 门槛；为避免选择偏差不计算行业结果"
            )
    d = d.dropna(subset=[MOM, "Scan_Date"])
    print(f"rows={len(d)} dates={d['Scan_Date'].nunique()} PIT_sector_coverage={sector_coverage:.2%}")

    if sector_ready:
        t1 = part1_turnover(d[d["Sector"].astype(str).str.strip().ne("")])
        if not t1:
            sector_reason = "PIT Sector 已加载，但有效的 Top/Bottom 行业 20D 样本不足"
        t3 = part3_attribution(d)
    else:
        t1 = {}
        t3 = {"status": "SKIPPED", "reason": sector_reason}
    print("part1:", t1 if t1 else {"status": "SKIPPED", "reason": sector_reason})
    print("part3:", t3)

    L = [
        "# 死亡解剖：换手率 / IC 衰减 / 归因\n",
        "> 脚本：`tools/research/turnover_and_cost_analysis.py`\n",
        "## 1. 行业轮动收益与换手成本\n",
    ]
    if t1:
        L += [
            "> 行业标签来自 `research_sector_history_pit.csv` 的有效日期区间；收益为每日 Top 3 行业多头减 Bottom 3 行业空头的平均 20D 前瞻收益。\n",
            "| 指标 | 值 |", "|---|---:|",
            f"| PIT 有效样本日期 | {t1.get('spread_samples', 0)} |",
            f"| 行业发生变化的日期间隔数 | {t1.get('changes', 0)} |",
            f"| 日均单边换手（行业权重代理） | {t1.get('avg_daily_single', float('nan')):.2f}% |",
            f"| 日均双边换手 | {t1.get('avg_daily_double', float('nan')):.2f}% |",
            f"| 20D 累计单边换手（近似） | {t1.get('cum20_single', float('nan')):.1f}% |",
            f"| 20D 累计双边换手（近似） | {t1.get('cum20_double', float('nan')):.1f}% |",
            f"| 20D 估计交易成本（双边 {COST_ONE_WAY * 100:.2f}%/次） | {t1.get('cost20_pct', float('nan')):.3f}% |",
            f"| 平均 20D 多空毛超额 | {t1.get('gross20_pct', float('nan')):+.4f}% |",
            f"| **平均 20D 多空净超额（毛收益−估计成本）** | **{t1.get('net20_pct', float('nan')):+.4f}%** |",
            "",
            "> 注意：行业换手是等权行业篮子的近似，不是逐只股票真实换手；结果仍需逐只股票的交易成本与容量检验。\n",
        ]
    else:
        L += [
            "⚠️ **本轮不计算行业轮动毛/净收益或换手成本。**",
            f"> 原因：{sector_reason or 'PIT 行业数据不可用'}。",
            "> 不允许把当前 `sp500_constituents.csv` 的现行行业标签套回两年历史，也不复用旧的硬编码 +0.1701% 毛超额。",
            "> 之前报告的 −0.184% 是基于当前行业映射的探索性估计，尚未通过 PIT 行业归属验证；不能把它当作已验证的净 Alpha 结论。\n",
        ]

    L += [
        "## 2. IC 衰减（数据受限）\\n",
        "⚠️ **无法生成完整的 T+1~T+20 连续衰减曲线**：",
        "`research_backtest_sp500_pit_2y.csv` 只提供 **5D / 10D / 20D** 三档前瞻收益，",
        "**没有逐日前瞻列** ⇒ 只能给出三点，无法定位【第几天衰减到 0】。",
        "IC 按每个 `Scan_Date` 单独计算横截面 Spearman 相关，再对日期取均值；不使用混合所有日期的 pooled correlation。\\n",
        "| 期限 | BP 日均 IC | BP 有效日期 | Momentum 日均 IC | Momentum 有效日期 | Momentum 正 IC 日期占比 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for h in (5, 10, 20):
        col = f"Forward_Return_{h}D"
        if col not in d.columns:
            L.append(f"| {h}D | N/A（缺 {col}） | 0 | N/A | 0 | N/A |")
            continue
        bp_ic = mean_daily_ic(d, "BP", col)
        mom_ic = mean_daily_ic(d, MOM, col)
        bp_value = f"{bp_ic['mean_ic']:+.4f}" if bp_ic["status"] == "OK" else "N/A"
        bp_dates = bp_ic.get("n_dates", 0)
        mom_value = f"{mom_ic['mean_ic']:+.4f}" if mom_ic["status"] == "OK" else "N/A"
        mom_dates = mom_ic.get("n_dates", 0)
        mom_positive = f"{mom_ic['positive_date_pct']:.1f}%" if mom_ic["status"] == "OK" else "N/A"
        L.append(f"| {h}D | {bp_value} | {bp_dates} | {mom_value} | {mom_dates} | {mom_positive} |")
    L += [
        "",
        "> 日均 IC 是因子预测相关性，不是扣成本后的可交易策略收益；不同日期的 IC 仍可能存在序列相关。\\n",
        "## 3. BP 归因回归（必须有真实 PIT 市值与 PIT 行业）\\n",
    ]
    if t3.get("status") == "OK":
        L += [
            f"> 样本 **{t3['n']:,}** 行；Size 使用真实 `Market_Cap` 的对数；Sector 为有效日期对应的 PIT 行业。\n",
            "| 模型 | BP 系数 | **BP 的 t 值** | R² |",
            "|---|---:|---:|---:|",
            f"| 仅 BP | {t3['BP_only']['coef']:.6f} | **{t3['BP_only']['t']:+.2f}** | {t3['BP_only']['r2']:.5f} |",
        ]
        if "BP+market_cap" in t3:
            L.append(f"| BP + Market Cap | {t3['BP+market_cap']['coef']:.6f} | **{t3['BP+market_cap']['t']:+.2f}** | {t3['BP+market_cap']['r2']:.5f} |")
        if "BP+market_cap+sector" in t3:
            L.append(f"| BP + Market Cap + PIT Sector | {t3['BP+market_cap+sector']['coef']:.6f} | **{t3['BP+market_cap+sector']['t']:+.2f}** | {t3['BP+market_cap+sector']['r2']:.5f} |")
    else:
        L += [
            "⚠️ **本轮不输出 BP 的风格调整 t 值。**",
            f"> 原因：{t3.get('reason', '真实 PIT 市值或 PIT 行业输入不可用')}。",
            "> 缺少 Market_Cap 时严格跳过；禁止继续把 `log(Price)` 当作 Size 代理。\n",
        ]

    L += [
        "## 4. 数据完整性与限制\n",
        "1. `research_sector_history_pit.csv` 必须含 `Ticker, Effective_From, Effective_To, Sector`；区间重叠、缺失或覆盖低于 99% 时不计算行业收益。",
        "2. 当前 `research_fundamentals_pit_corrected.csv` 若没有真实 `Market_Cap`，BP 市值归因会跳过，不会用 `log(Price)` 静默替代。",
        "3. 现有换手模型只估算等权行业篮子的权重更换，非个股级订单流或实际成交成本。",
        "4. IC 衰减只有 5D / 10D / 20D 三个点；缺少每日前瞻收益时不推断更短衰减期。",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
