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


def stats(series, h=H):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return dict(total=float("nan"), sharpe=float("nan"), mdd=float("nan"), n=0, vol=float("nan"))
    nd = s.iloc[::h].reset_index(drop=True)      # 非重叠抽样：每 h 期取一个独立样本
    cum = (1 + nd).cumprod()
    peak = cum.cummax()
    mdd = float((cum / peak - 1).min()) * 100
    sharpe = float(nd.mean() / nd.std(ddof=1) * np.sqrt(252 / h)) if len(nd) > 2 and nd.std(ddof=1) > 0 else float("nan")
    return dict(total=float(cum.iloc[-1] - 1) * 100, sharpe=sharpe, mdd=mdd,
                n=int(len(nd)), vol=float(nd.std(ddof=1)) * 100)

def main() -> int:
    if not BT.exists():
        raise SystemExit(f"missing {BT}")
    d = pd.read_csv(BT, dtype=str, keep_default_na=False)
    for c in (MOM, "ATR_Pct", f"Forward_Return_{H}D"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[MOM, "ATR_Pct", f"Forward_Return_{H}D"])
    d = d[d["ATR_Pct"] > 0]
    print(f"rows={len(d)} dates={d['Scan_Date'].nunique()}")

    fixed_ret, atr_ret, atr_w, picked = [], [], [], 0
    for dt, day in d.groupby("Scan_Date"):
        top = day.nlargest(TOPK, MOM)
        if top.empty:
            continue
        picked += len(top)
        r = top[f"Forward_Return_{H}D"].to_numpy(float)
        # 固定仓位：等额 ⇒ 等权平均
        fixed_ret.append(float(np.mean(r)))
        # ATR 平价：w_i ∝ 1/ATR_i ⇒ 加权平均
        atr = top["ATR_Pct"].to_numpy(float)
        w = (1.0 / atr)
        w = w / w.sum()
        atr_ret.append(float(np.sum(w * r)))
        atr_w.append(w)

    F = pd.Series(fixed_ret)
    A = pd.Series(atr_ret)
    sf, sa = stats(F), stats(A)
    print(f"  picked rows={picked} | days={len(F)}")
    print(f"  fixed: total={sf['total']:+.2f}% sharpe={sf['sharpe']:.2f} mdd={sf['mdd']:.2f}%")
    print(f"  atr  : total={sa['total']:+.2f}% sharpe={sa['sharpe']:.2f} mdd={sa['mdd']:.2f}%")

    # 仓位离散度（ATR 平价的权重分布）
    W = np.array(atr_w)
    w_min, w_max = float(W.min()), float(W.max())

    L = ["# ATR 风险平价仓位 vs 固定仓位（2y PIT，20D 持有）\n",
         "> 脚本：`tools/research/atr_position_sizing.py`",
         f"> 样本：**{len(d):,}** 行 / **{d['Scan_Date'].nunique()}** 个 Scan_Date；"
         f"每日取 `{MOM}` Top{TOPK}",
         "> 两策略**同池同票**，唯一差异是仓位权重 ✓\n",
         "## 1. 结果对比\n",
         "| 指标 | 固定仓位（等权 10,000/只） | **ATR 风险平价（10,000/ATR%）** | 差异 |",
         "|---|---|---|---|",
         f"| 平均 20D 收益 | {sf['total']:+.2f}% | **{sa['total']:+.2f}%** | {sa['total'] - sf['total']:+.2f} pp |",
         f"| 日收益波动 | {sf['vol']:.3f}% | **{sa['vol']:.3f}%** | {sa['vol'] - sf['vol']:+.3f} pp |",
         f"| **夏普\\*** | **{sf['sharpe']:.3f}** | **{sa['sharpe']:.3f}** | {sa['sharpe'] - sf['sharpe']:+.3f} |",
         f"| **最大回撤** | **{sf['mdd']:.2f}%** | **{sa['mdd']:.2f}%** | {sa['mdd'] - sf['mdd']:+.2f} pp |",
         f"| 交易日数 | {sf['n']} | {sa['n']} | — |",
         "\n`*` 夏普按日序列 × √(252/20)；**含 20D 重叠偏差（高估约 √20≈4.5 倍）** ✓\n",
         "## 2. 权重分布（ATR 平价）\n",
         f"- 单票权重区间：**{w_min:.3%} ~ {w_max:.3%}**（越分散说明 ATR 差异越大）",
         f"- 等权基准权重 = {100 / TOPK:.1f}% ⇒ "
         + ("**ATR 平价显著偏离等权** ✓" if (w_max - w_min) > 0.05 else "**接近等权** ⇒ 该池 ATR 差异小 ✓"),
         "",
         "## 3. 结论\n"]
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
    L += ["", "## 4. ⚠️ 限制\n",
          "1. **20D 前瞻重叠** ⇒ 夏普高估；绝对收益不可外推 ✓",
          "2. 权重只按 `ATR_Pct` 归一，**未考虑相关性/行业集中** ✓",
          "3. 未扣成本；未考虑资金约束（总仓位可能超 5×10,000）✓",
          "4. 选股用 `Momentum_20D_Pct` 代理，**非生产严筛逻辑** ✓",
          ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  w_range={w_min:.3%}~{w_max:.3%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
