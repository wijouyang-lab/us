#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史因子 IC 分析（2 年）

直接复用 quant_factor_backtest.run_backtest_from_history，
用独立研究文件（不碰生产 quant_factor_snapshot.csv / quant_factor_price_history.csv）。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def main():
    snap = REPO / "research_factor_snapshots_2y.csv"
    price = REPO / "research_price_history_2y.csv"
    backtest = REPO / "research_backtest_2y.csv"
    summary = REPO / "research_summary_2y.csv"

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
