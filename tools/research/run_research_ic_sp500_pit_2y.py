#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S&P 500 点内（PIT）版 · IC 流程入口

调用 quant_factor_backtest.run_backtest_from_history 生成
research_backtest_sp500_pit_2y.csv / research_summary_sp500_pit_2y.csv，
随后调用 compute_ic_sp500_pit_2y 重算 IC 表 research_ic_sp500_pit_2y.csv。

与 S&P500 静态版的唯一差异 = 4 个路径常量 + 末尾 import 的模块名。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def main():
    snap = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
    price = REPO / "research_price_history_sp500_2y.csv"
    backtest = REPO / "research_backtest_sp500_pit_2y.csv"
    summary = REPO / "research_summary_sp500_pit_2y.csv"

    if not snap.exists():
        print(f"missing: {snap}")
        return 1
    if not price.exists():
        print(f"missing: {price}")
        return 1

    from quant_factor_backtest import run_backtest_from_history

    print(f"snapshot: {snap} ({snap.stat().st_size} bytes)")
    print(f"price:    {price} ({price.stat().st_size} bytes)")

    run_backtest_from_history(
        snapshot_path=str(snap),
        price_history_path=str(price),
        backtest_path=str(backtest),
        summary_path=str(summary),
    )

    print(f"OK: {backtest.name} / {summary.name}")
    if backtest.exists():
        print(f"  backtest: {backtest.stat().st_size} bytes")
    if summary.exists():
        print(f"  summary:  {summary.stat().st_size} bytes")
        print("  --- summary 前 30 行 ---")
        with open(summary, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 30:
                    break
                print(f"    {line.rstrip()}")

    # 追加：调用 compute_ic_sp500_pit_2y 重算 IC 表（17 因子；前瞻收益只从 backtest CSV 搬运）
    try:
        import compute_ic_sp500_pit_2y
        compute_ic_sp500_pit_2y.main()
    except Exception as e:
        print(f"[warn] compute_ic_sp500_pit_2y failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
