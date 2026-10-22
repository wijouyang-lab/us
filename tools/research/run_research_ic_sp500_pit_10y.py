#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S&P 500 点内（PIT）10 年版 · IC 流程入口（合并 workflow 用）

调用 quant_factor_backtest.run_backtest_from_history 生成
research_backtest_sp500_pit_10y.csv / research_summary_sp500_pit_10y.csv，
随后调用 compute_ic_sp500_pit_10y 重算 IC 表 research_ic_sp500_pit_10y.csv。

注意：10 年快照（188 MB）走 artifact 不入库；IC 表（几 KB）才入库。
与 PIT 2 年版的唯一差异 = 4 个路径常量 + 末尾 import 的模块名。
"""
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def main():
    snap = REPO / "research_factor_snapshots_sp500_pit_10y.csv"
    price = REPO / "research_price_history_sp500_10y.csv"
    backtest = REPO / "research_backtest_sp500_pit_10y.csv"
    summary = REPO / "research_summary_sp500_pit_10y.csv"

    if not snap.exists():
        print(f"missing: {snap}")
        return 1
    if not price.exists():
        print(f"missing: {price}")
        return 1

    import pandas as pd
    from quant_factor_backtest import run_backtest
    from quant_factor_price import price_map_from_history

    print(f"snapshot: {snap} ({snap.stat().st_size} bytes)")
    print(f"price:    {price} ({price.stat().st_size} bytes)")

    # Keep raw OHLC-derived factors unchanged. Only forward-return labels use
    # adjusted closes, and the original snapshot CSV is never overwritten.
    snap_df = pd.read_csv(snap, dtype=str, keep_default_na=False)
    price_df = pd.read_csv(price, dtype=str, keep_default_na=False)
    required_snapshot_cols = {"Ticker", "Technical_Date", "Price"}
    missing_snapshot_cols = sorted(required_snapshot_cols - set(snap_df.columns))
    if missing_snapshot_cols:
        raise ValueError(f"10Y research snapshot missing columns: {missing_snapshot_cols}")
    required_price_cols = {"Date", "Ticker", "Close", "Adj Close", "Price_Basis"}
    missing_price_cols = sorted(required_price_cols - set(price_df.columns))
    if missing_price_cols:
        raise ValueError(f"10Y research price history missing columns: {missing_price_cols}")
    basis = sorted(set(price_df["Price_Basis"].astype(str).str.strip()))
    if basis != ["raw_ohlc_adj_close"]:
        raise ValueError(f"Unexpected 10Y research price basis: {basis}")

    snap_df["Ticker"] = snap_df["Ticker"].astype(str).str.strip().str.upper()
    snap_df["Technical_Date"] = pd.to_datetime(snap_df["Technical_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    price_df["Ticker"] = price_df["Ticker"].astype(str).str.strip().str.upper()
    price_df["Date"] = pd.to_datetime(price_df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    price_df["Adj Close"] = pd.to_numeric(price_df["Adj Close"], errors="coerce")
    price_df = price_df.dropna(subset=["Date", "Ticker", "Adj Close"])
    if price_df.duplicated(["Ticker", "Date"]).any():
        raise ValueError("duplicate Ticker/Date keys in 10Y research price history")

    adjusted_close = price_df[["Ticker", "Date", "Adj Close"]].rename(
        columns={"Date": "Technical_Date"}
    )
    adjusted_close = adjusted_close.drop_duplicates(["Ticker", "Technical_Date"])
    joined = snap_df[["Ticker", "Technical_Date"]].merge(
        adjusted_close, on=["Ticker", "Technical_Date"], how="left", validate="one_to_one"
    )
    if joined["Adj Close"].isna().any() or (joined["Adj Close"] <= 0).any():
        examples = joined.loc[
            joined["Adj Close"].isna() | (joined["Adj Close"] <= 0),
            ["Ticker", "Technical_Date", "Adj Close"],
        ].head(10).to_dict("records")
        raise ValueError(
            f"Adjusted close missing/invalid for {int((joined['Adj Close'].isna() | (joined['Adj Close'] <= 0)).sum())} snapshot rows; examples={examples}"
        )
    snap_df["Price"] = joined["Adj Close"].map(lambda value: f"{float(value):.8f}")
    adjusted_prices = price_df[["Date", "Ticker", "Adj Close"]].rename(
        columns={"Adj Close": "Close"}
    )
    price_map = price_map_from_history(adjusted_prices)

    with tempfile.TemporaryDirectory(prefix="pit-adjusted-backtest-") as tmpdir:
        temp_snapshot = Path(tmpdir) / "research_factor_snapshots_sp500_pit_10y.adjusted-labels.csv"
        snap_df.to_csv(temp_snapshot, index=False, encoding="utf-8")
        result = run_backtest(
            snapshot_path=str(temp_snapshot),
            price_map=price_map,
            backtest_path=str(backtest),
            summary_path=str(summary),
        )
    if result.get("status") != "OK" or not result.get("written"):
        raise RuntimeError(f"10Y research backtest did not produce output: {result}")
    if not backtest.exists() or backtest.stat().st_size == 0:
        raise RuntimeError("10Y research backtest output is missing or empty")
    print(f"OK: {backtest.name} / {summary.name}; rows={result.get('backtest_rows')}")
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

    # 追加：调用 compute_ic_sp500_pit_10y 重算 IC 表（前瞻收益只从 backtest CSV 搬运）
    import compute_ic_sp500_pit_10y
    ic_status = compute_ic_sp500_pit_10y.main()
    if ic_status not in (None, 0):
        raise RuntimeError(f"10Y IC calculation failed with exit code {ic_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
