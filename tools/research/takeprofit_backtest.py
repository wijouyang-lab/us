#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""止盈模块回测：4 套规则 vs 2 个基准

信号：每日 ATR_Pct 截面 Top 5
持仓：最多 5 只，每只最长 20 日
止损：-8%

【与规格的唯一差异（已声明）】
原稿在 run_backtest 内对每个交易日执行 `df[df[Scan_Date] == d]`
（1,047,578 行 × 2,472 天 ≈ 26 亿次比较 → 预计数小时）。
此处改为**一次性 groupby 预分组**后按日期取用，逐 bit 保持同一逻辑：
  day_df = day_groups[d].copy()   ← 等价于 df[df[DATE_COL] == d].copy()
其余（选股、持仓、止盈/止损判定、汇总口径）完全照原样。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
MAX_POSITIONS = 5
MAX_HOLD_DAYS = 20
STOP_LOSS_PCT = -8.0
ATR_COL = "ATR_Pct"
DATE_COL = "Scan_Date"
TICKER_COL = "Ticker"
RET_5D = "Forward_Return_5D"


def simulate_one_trade(prices, entry_idx, max_hold, stop_pct, tp_rule):
    """模拟单笔交易，返回 (exit_idx, exit_reason, pnl_pct)

    prices: np.array，该股从入场日开始的后续价格（含入场价）
    """
    entry_price = prices[0]
    peak = entry_price
    for i in range(1, min(len(prices), max_hold + 1)):
        cur = prices[i]
        peak = max(peak, cur)
        ret = (cur - entry_price) / entry_price * 100
        peak_ret = (peak - entry_price) / entry_price * 100

        # 止损
        if ret <= stop_pct:
            return i, "stop_loss", ret

        # 止盈规则
        if tp_rule["type"] == "fixed":
            if ret >= tp_rule["threshold"]:
                return i, "tp_fixed", ret
        elif tp_rule["type"] == "trailing":
            drawdown_from_peak = (peak - cur) / peak * 100
            if drawdown_from_peak >= tp_rule["dd"] and peak_ret > 0:
                return i, "tp_trailing", ret
        elif tp_rule["type"] == "partial":
            if ret >= tp_rule["threshold_1"]:
                return i, "tp_partial_1", ret

    # 到期
    exit_idx = min(len(prices) - 1, max_hold)
    return exit_idx, "timeout", (prices[exit_idx] - entry_price) / entry_price * 100


def run_backtest(df, tp_rule, label):
    """用每日信号跑回测"""
    dates = sorted(df[DATE_COL].unique())
    ticker_date_price = df.set_index([TICKER_COL, DATE_COL])["Price"].to_dict()
    ticker_date_atr = df.set_index([TICKER_COL, DATE_COL])[ATR_COL].to_dict()
    # 【性能修正】一次性预分组，替代逐日全表扫描（逻辑等价）
    day_groups = {d: g for d, g in df.groupby(DATE_COL, sort=False)}

    open_positions = {}  # ticker -> {entry_date, entry_price, entry_idx}
    trades = []

    for di, d in enumerate(dates):
        day_df = day_groups.get(d)
        if day_df is None or day_df.empty:
            continue
        day_df = day_df.copy()
        day_df[ATR_COL] = pd.to_numeric(day_df[ATR_COL], errors="coerce")
        day_df = day_df.dropna(subset=[ATR_COL])
        if day_df.empty:
            continue

        # 更新持仓
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
            # 只有"实际到今天已触发"才关仓
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

        # 开新仓
        if len(open_positions) < MAX_POSITIONS:
            top = day_df.nlargest(MAX_POSITIONS - len(open_positions), ATR_COL)
            for _, row in top.iterrows():
                tk = row[TICKER_COL]
                if tk in open_positions:
                    continue
                open_positions[tk] = {
                    "entry_date": d,
                    "entry_price": row["Price"],
                    "entry_idx": di,
                }

    # 汇总
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

    RULES = {
        "baseline_none": {"type": "none"},  # 纯止损+持有
        "A_fixed_10": {"type": "fixed", "threshold": 10.0},
        "A_fixed_15": {"type": "fixed", "threshold": 15.0},
        "A_fixed_20": {"type": "fixed", "threshold": 20.0},
        "C_trailing_5": {"type": "trailing", "dd": 5.0},
        "C_trailing_8": {"type": "trailing", "dd": 8.0},
        "C_trailing_10": {"type": "trailing", "dd": 10.0},
    }

    for label, rule in RULES.items():
        run_backtest(df, rule, label)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
