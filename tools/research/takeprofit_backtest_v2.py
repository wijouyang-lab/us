#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""止盈模块回测 v2：用 S&P500 全池（随机等权 N=20）作为底层信号

v1 的问题：用 ATR_Pct Top5 选股 → 底层信号夏普仅 0.47 → 止盈无法验证。
v2 的改动：**不做选股**，每日从全池随机抽 N=20 只等权买入（seed=42 可复现），
          底层即 S&P500 市场 beta（正期望）→ 止盈结论才具参考价值。

止盈规则与 v1 **完全相同**（1 基准 + 3 固定 + 3 移动），
模拟引擎直接 import v1 的 simulate_one_trade，避免口径漂移。

【性能】与 v1 相同做法：一次性 groupby 预分组，替代逐日全表扫描。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "research"))

from takeprofit_backtest import simulate_one_trade  # noqa: E402  （v1 引擎，口径一致）

MAX_POSITIONS = 20          # 每日等权买入 20 只（每只 5%）
MAX_HOLD_DAYS = 20
STOP_LOSS_PCT = -8.0
SEED = 42
ATR_COL = "ATR_Pct"
DATE_COL = "Scan_Date"
TICKER_COL = "Ticker"
RET_5D = "Forward_Return_5D"


def run_backtest_v2(df, tp_rule, label):
    """每日随机抽 MAX_POSITIONS 只等权买入；止盈/止损/到期同 v1。"""
    dates = sorted(df[DATE_COL].unique())
    ticker_date_price = df.set_index([TICKER_COL, DATE_COL])["Price"].to_dict()
    day_groups = {d: g for d, g in df.groupby(DATE_COL, sort=False)}
    rng = np.random.RandomState(SEED)

    open_positions = {}
    trades = []

    for di, d in enumerate(dates):
        day_df = day_groups.get(d)
        if day_df is None or day_df.empty:
            continue

        # 更新持仓（同 v1）
        to_close = []
        for tk, pos in open_positions.items():
            future_prices = []
            for dd in dates[pos["entry_idx"]:di + 1]:
                p = ticker_date_price.get((tk, dd))
                if p is not None:
                    future_prices.append(p)
            if len(future_prices) < 2:
                continue
            exit_idx, reason, pnl = simulate_one_trade(
                future_prices, 0, MAX_HOLD_DAYS, STOP_LOSS_PCT, tp_rule
            )
            if exit_idx < len(future_prices) - 1 or exit_idx == MAX_HOLD_DAYS:
                to_close.append((tk, reason, pnl, exit_idx))

        for tk, reason, pnl, exit_idx in to_close:
            trades.append({
                "ticker": tk,
                "entry_date": open_positions[tk]["entry_date"],
                "exit_date": dates[open_positions[tk]["entry_idx"] + exit_idx],
                "pnl_pct": pnl,
                "reason": reason,
                "hold_days": exit_idx,
            })
            del open_positions[tk]

        # 开新仓：**随机等权**（非 ATR 选股）
        slots = MAX_POSITIONS - len(open_positions)
        if slots > 0:
            cand = day_df[~day_df[TICKER_COL].isin(open_positions.keys())]
            if not cand.empty:
                take = cand.sample(n=min(slots, len(cand)), random_state=rng.randint(0, 2**31 - 1))
                for _, row in take.iterrows():
                    open_positions[row[TICKER_COL]] = {
                        "entry_date": d,
                        "entry_price": row["Price"],
                        "entry_idx": di,
                    }

    if not trades:
        print(f"[{label}] 无交易")
        return None
    tdf = pd.DataFrame(trades)
    mean_ret = tdf["pnl_pct"].mean()
    std_ret = tdf["pnl_pct"].std()
    win_rate = (tdf["pnl_pct"] > 0).mean() * 100
    sharpe = mean_ret / std_ret * np.sqrt(252 / MAX_HOLD_DAYS) if std_ret > 0 else 0
    cum = (1 + tdf["pnl_pct"] / 100).cumprod()
    drawdown = (cum / cum.cummax() - 1).min() * 100
    print(f"[{label}]")
    print(f"  交易数: {len(tdf)}")
    print(f"  平均收益: {mean_ret:+.3f}%")
    print(f"  中位收益: {tdf['pnl_pct'].median():+.3f}%")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  年化夏普: {sharpe:.2f}")
    print(f"  最大回撤(交易序列): {drawdown:.2f}%")
    print(f"  平均持仓天数: {tdf['hold_days'].mean():.1f}")
    print(f"  退出原因分布:")
    for r, c in tdf["reason"].value_counts().items():
        print(f"    {r}: {c}")
    return tdf


def main():
    print("Loading backtest data...")
    df = pd.read_csv("bt_pit_10y.csv", dtype=str, encoding="utf-8-sig", usecols=[
        DATE_COL, TICKER_COL, "Price", ATR_COL, RET_5D
    ])
    df = df.dropna(subset=[DATE_COL, TICKER_COL])
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df = df.dropna(subset=["Price"])
    print(f"loaded {len(df)} rows, {df[DATE_COL].nunique()} days")
    print(f"v2: 随机等权 N={MAX_POSITIONS}（seed={SEED}）/ 最长持有 {MAX_HOLD_DAYS} 日 / 止损 {STOP_LOSS_PCT}%")
    print()

    RULES = {
        "baseline_none": {"type": "none"},
        "A_fixed_10": {"type": "fixed", "threshold": 10.0},
        "A_fixed_15": {"type": "fixed", "threshold": 15.0},
        "A_fixed_20": {"type": "fixed", "threshold": 20.0},
        "C_trailing_5": {"type": "trailing", "dd": 5.0},
        "C_trailing_8": {"type": "trailing", "dd": 8.0},
        "C_trailing_10": {"type": "trailing", "dd": 10.0},
    }

    for label, rule in RULES.items():
        run_backtest_v2(df, rule, label)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
