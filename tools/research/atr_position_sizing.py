#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR 风险平价仓位 vs 固定仓位：2y PIT 回测对比（只读）。

策略口径（两支独立模拟，同日同票，仅仓位不同）：
  · 原策略（固定）：每日取 Composite/Momentum 排名前 5 只，每只固定 10,000 名义
  · 新策略（ATR 平价）：每只名义 = 10,000 / (ATR_Pct/1%)  （波动越大买得越少）
  · 持有 20D，按 Forward_Return_20D 计算组合收益（日度序列，重叠偏差已标注）

数据：research_backtest_sp500_pit_2y.csv（含 ATR_Pct / Forward_Return_20D / Momentum_20D_Pct）
输出：docs/ATR_POSITION_SIZING.md
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
BT = REPO / "research_backtest_sp500_pit_2y.csv"
OUT = REPO / "docs" / "ATR_POSITION_SIZING.md"

TOPK = 5
H = 20
UNIT = 10000.0
MOM = "Momentum_20D_Pct"
ROUND_TRIP_COST_BPS = float(os.environ.get("QUANT_ROUND_TRIP_COST_BPS", "11.0"))
if not np.isfinite(ROUND_TRIP_COST_BPS) or ROUND_TRIP_COST_BPS < 0:
    raise ValueError("QUANT_ROUND_TRIP_COST_BPS must be a finite non-negative number")


def stats(series, h=H):
    """Stats for non-overlapping h-day portfolio returns (returns are decimal fractions)."""
    s = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    if s.empty:
        return dict(total=float("nan"), mean_period=float("nan"), sharpe=float("nan"),
                    mdd=float("nan"), n=0, vol=float("nan"))
    nd = s.iloc[::h].reset_index(drop=True)
    cum = (1 + nd).cumprod()
    # Include initial equity=1.0 so a loss in the first holding period counts as drawdown.
    equity_with_start = pd.concat([pd.Series([1.0]), cum], ignore_index=True)
    peak = equity_with_start.cummax().iloc[1:].reset_index(drop=True)
    mdd = float((cum / peak - 1).min()) * 100
    std = float(nd.std(ddof=1)) if len(nd) > 1 else float("nan")
    sharpe = float(nd.mean() / std * np.sqrt(252 / h)) if len(nd) > 2 and np.isfinite(std) and std > 0 else float("nan")
    return dict(total=float(cum.iloc[-1] - 1) * 100, mean_period=float(nd.mean()) * 100,
                sharpe=sharpe, mdd=mdd, n=int(len(nd)), vol=std * 100)

def main() -> int:
    if not BT.exists():
        raise SystemExit(f"missing {BT}")
    d = pd.read_csv(BT, dtype=str, keep_default_na=False)
    for c in (MOM, "ATR_Pct", f"Forward_Return_{H}D"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[MOM, "ATR_Pct", f"Forward_Return_{H}D"])
    d = d[d["ATR_Pct"] > 0]
    print(f"rows={len(d)} dates={d['Scan_Date'].nunique()}")

    fixed_gross, atr_gross, atr_w, picked = [], [], [], 0
    for dt, day in d.groupby("Scan_Date"):
        top = day.nlargest(TOPK, MOM)
        if top.empty:
            continue
        picked += len(top)
        r = top[f"Forward_Return_{H}D"].to_numpy(float)
        # 固定仓位：等额 ⇒ 等权平均
        fixed_gross.append(float(np.mean(r)))
        # ATR 平价：w_i ∝ 1/ATR_i ⇒ 加权平均
        atr = top["ATR_Pct"].to_numpy(float)
        w = (1.0 / atr)
        w = w / w.sum()
        atr_gross.append(float(np.sum(w * r)))
        atr_w.append(w)

    Fg = pd.Series(fixed_gross)
    Ag = pd.Series(atr_gross)
    cost_fraction = ROUND_TRIP_COST_BPS / 10000.0
    Fn = Fg - cost_fraction
    An = Ag - cost_fraction
    sfg, sag = stats(Fg), stats(Ag)
    sf, sa = stats(Fn), stats(An)
    print(f"  picked rows={picked} | scan_dates={len(Fg)} | nonoverlap_periods={sf['n']}")
    print(f"  round_trip_cost={ROUND_TRIP_COST_BPS:.2f} bps per 20D holding period")
    print(f"  fixed: gross_total={sfg['total']:+.2f}% net_total={sf['total']:+.2f}% net_sharpe={sf['sharpe']:.2f} net_mdd={sf['mdd']:.2f}%")
    print(f"  atr  : gross_total={sag['total']:+.2f}% net_total={sa['total']:+.2f}% net_sharpe={sa['sharpe']:.2f} net_mdd={sa['mdd']:.2f}%")

    # Cost sensitivity across plausible round-trip assumptions; models only, not broker quotes.
    cost_sensitivity = []
    for scenario_bps in sorted(set([ROUND_TRIP_COST_BPS, 25.0, 50.0, 100.0])):
        fixed_s = stats(Fg - scenario_bps / 10000.0)
        atr_s = stats(Ag - scenario_bps / 10000.0)
        cost_sensitivity.append((scenario_bps, fixed_s, atr_s))

    # 仓位离散度（ATR 平价的权重分布）
    W = np.array(atr_w)
    w_min, w_max = float(W.min()), float(W.max())

    L = [
        "# ATR 风险平价仓位 vs 固定仓位（2y PIT，20D 持有）\n",
        "> 脚本：tools/research/atr_position_sizing.py",
        f"> 样本：**{len(d):,}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date；每日取 {MOM} Top{TOPK}",
        "> 两策略同池同票，唯一差异是仓位权重。",
        "## 1. 结果对比\n",
        f"> 交易成本假设：每个完整 20D 持有期往返 {ROUND_TRIP_COST_BPS:.1f} bps（进场滑点 5 bps + 出场滑点 5 bps + 双边佣金 1 bps）。这是模型假设，不是券商报价。\n",
        "| 指标 | 固定仓位（等权 Top5） | ATR 风险平价 Top5 | 差异 |",
        "|---|---:|---:|---:|",
        f"| 平均单期 20D 毛收益 | {sfg['mean_period']:+.3f}% | {sag['mean_period']:+.3f}% | {sag['mean_period'] - sfg['mean_period']:+.3f} pp |",
        f"| 平均单期 20D 净收益 | {sf['mean_period']:+.3f}% | {sa['mean_period']:+.3f}% | {sa['mean_period'] - sf['mean_period']:+.3f} pp |",
        f"| 非重叠 20D 期累计净复利 | {sf['total']:+.2f}% | {sa['total']:+.2f}% | {sa['total'] - sf['total']:+.2f} pp |",
        f"| 非重叠 20D 净收益标准差 | {sf['vol']:.3f}% | {sa['vol']:.3f}% | {sa['vol'] - sf['vol']:+.3f} pp |",
        f"| 夏普（净收益） | {sf['sharpe']:.3f} | {sa['sharpe']:.3f} | {sa['sharpe'] - sf['sharpe']:+.3f} |",
        f"| 最大回撤（净收益） | {sf['mdd']:.2f}% | {sa['mdd']:.2f}% | {sa['mdd'] - sf['mdd']:+.2f} pp |",
        f"| 非重叠 20D 持有期数量 | {sf['n']} | {sa['n']} | — |",
        "\n夏普按非重叠 20D 持有期收益 × √(252/20) 年化；单期收益不是日收益。\n",
        "## 2. 权重分布（ATR 平价）\n",
        f"- 单票权重区间：**{w_min:.3%} ~ {w_max:.3%}**",
        f"- 等权基准权重 = {100 / TOPK:.1f}% ⇒ " + ("ATR 平价显著偏离等权" if (w_max - w_min) > 0.05 else "接近等权"),
        "",
        "## 4. 结论\n",
    ]
    L += [
        "## 3. 交易成本敏感性\n",
        "> 每个场景的 bps 是一个完整 20D 持有期的往返成本；不代表实际券商报价。",
        "| 往返成本（bps） | 固定仓位平均净 20D | 固定仓位累计净复利 | 固定仓位净夏普 | ATR 平均净 20D | ATR 累计净复利 | ATR 净夏普 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario_bps, fixed_s, atr_s in cost_sensitivity:
        L.append(
            f"| {scenario_bps:.1f} | {fixed_s['mean_period']:+.3f}% | {fixed_s['total']:+.2f}% | "
            f"{fixed_s['sharpe']:.3f} | {atr_s['mean_period']:+.3f}% | {atr_s['total']:+.2f}% | "
            f"{atr_s['sharpe']:.3f} |"
        )
    L += [
        "",
        "> 成本敏感性只用于检验结论对假设的依赖程度；不补足市场冲击、流动性、税费或真实订单回报。\n",
    ]

    if pd.notna(sa["sharpe"]) and pd.notna(sf["sharpe"]):
        if sa["sharpe"] > sf["sharpe"]:
            L.append(f"- ✅ **ATR 平价提升夏普**：{sf['sharpe']:.3f} → **{sa['sharpe']:.3f}**"
                     f"（+{sa['sharpe'] - sf['sharpe']:.3f}）✓")
        else:
            L.append(f"- ✗ **ATR 平价未提升夏普**：{sf['sharpe']:.3f} → {sa['sharpe']:.3f}"
                     f"（{sa['sharpe'] - sf['sharpe']:+.3f}）")
        L.append(f"- 回撤变化：{sf['mdd']:.2f}% → **{sa['mdd']:.2f}%**"
                 + ("（**改善** ✓）" if sa["mdd"] > sf["mdd"] else "（**恶化** ✗）"))
        L.append(f"- 收益变化：{sf['total']:+.2f}% → {sa['total']:+.2f}%")
    L += ["", "## 5. ⚠️ 限制\n",
          "1. 从每日滚动 20D 前瞻收益每隔 20 个 Scan_Date 抽样形成非重叠期近似；这不是完整逐日组合权益曲线，绝对收益不可外推。",
          "2. 权重只按 `ATR_Pct` 归一，**未考虑相关性/行业集中** ✓",
          f"3. 已扣除每个 20D 持有期往返 {ROUND_TRIP_COST_BPS:.1f} bps；仍未考虑市场冲击、税费与资金约束（总仓位可能超 5×10,000）✓",
          "4. 选股用 `Momentum_20D_Pct` 代理，**非生产严筛逻辑** ✓",
          ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  w_range={w_min:.3%}~{w_max:.3%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
