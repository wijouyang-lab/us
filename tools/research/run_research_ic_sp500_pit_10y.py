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

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def prepare_adjusted_label_inputs(snapshot_df, price_df):
    """Return a temporary adjusted-label snapshot and an adjusted-close price table.

    Factor values and raw snapshot files are left unchanged. Only the copy's Price
    field is replaced with the same session's Adj Close, so forward-return labels
    compare adjusted values on both T and T+N.
    """
    required_snapshot_cols = {"Ticker", "Technical_Date", "Price"}
    missing_snapshot_cols = sorted(required_snapshot_cols - set(snapshot_df.columns))
    if missing_snapshot_cols:
        raise ValueError(f"10Y research snapshot missing columns: {missing_snapshot_cols}")
    required_price_cols = {"Date", "Ticker", "Close", "Adj Close", "Price_Basis"}
    missing_price_cols = sorted(required_price_cols - set(price_df.columns))
    if missing_price_cols:
        raise ValueError(f"10Y research price history missing columns: {missing_price_cols}")
    basis = sorted(set(price_df["Price_Basis"].astype(str).str.strip()))
    if basis != ["raw_ohlc_adj_close"]:
        raise ValueError(f"Unexpected 10Y research price basis: {basis}")

    snapshot = snapshot_df.copy()
    prices = price_df.copy()
    snapshot["Ticker"] = snapshot["Ticker"].astype(str).str.strip().str.upper()
    snapshot["Technical_Date"] = pd.to_datetime(
        snapshot["Technical_Date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    prices["Ticker"] = prices["Ticker"].astype(str).str.strip().str.upper()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    prices["Adj Close"] = pd.to_numeric(prices["Adj Close"], errors="coerce")
    prices = prices.dropna(subset=["Date", "Ticker", "Adj Close"])
    if prices.duplicated(["Ticker", "Date"]).any():
        raise ValueError("duplicate Ticker/Date keys in 10Y research price history")

    row_key = "__pit_research_row_order__"
    if row_key in snapshot.columns:
        raise ValueError(f"snapshot contains reserved helper column: {row_key}")
    snapshot[row_key] = range(len(snapshot))
    adjusted_close = prices[["Ticker", "Date", "Adj Close"]].rename(
        columns={"Date": "Technical_Date"}
    )
    joined = snapshot[[row_key, "Ticker", "Technical_Date"]].merge(
        adjusted_close, on=["Ticker", "Technical_Date"], how="left", validate="many_to_one"
    ).sort_values(row_key)
    missing = joined["Adj Close"].isna() | (joined["Adj Close"] <= 0)
    if missing.any():
        examples = joined.loc[
            missing, ["Ticker", "Technical_Date", "Adj Close"]
        ].head(10).to_dict("records")
        raise ValueError(
            f"Adjusted close missing/invalid for {int(missing.sum())} snapshot rows; examples={examples}"
        )
    snapshot["Price"] = joined["Adj Close"].map(lambda value: f"{float(value):.8f}").to_numpy()
    snapshot = snapshot.drop(columns=[row_key])
    adjusted_prices = prices[["Date", "Ticker", "Adj Close"]].rename(
        columns={"Adj Close": "Close"}
    )
    return snapshot, adjusted_prices


def build_market_aligned_adjusted_price_map(adjusted_prices, market_dates):
    """Align adjusted stock closes to every SPY session, preserving missing bars as NaN.

    This makes an N-session return mean N market sessions later. A missing stock bar
    yields a missing label instead of silently shifting the horizon to a later date.
    """
    parsed_market_dates = pd.to_datetime(pd.Series(list(market_dates)), errors="coerce").dropna()
    market_index = pd.DatetimeIndex(sorted(parsed_market_dates.drop_duplicates().tolist()))
    if market_index.empty:
        raise ValueError("SPY market-session calendar is empty")

    prices = adjusted_prices.copy()
    prices["Ticker"] = prices["Ticker"].astype(str).str.strip().str.upper()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Date", "Ticker"])
    if prices.duplicated(["Ticker", "Date"]).any():
        raise ValueError("duplicate Ticker/Date keys in adjusted return price map")

    aligned = {}
    for ticker, group in prices.groupby("Ticker", sort=False):
        series = group.set_index("Date")["Close"].sort_index()
        aligned[str(ticker)] = series.reindex(market_index)
    return aligned


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
    from quant_factor_backtest import forward_return_nd

    print(f"snapshot: {snap} ({snap.stat().st_size} bytes)")
    print(f"price:    {price} ({price.stat().st_size} bytes)")

    # Keep raw OHLC-derived factors unchanged. Only forward-return labels use
    # adjusted closes, and the original snapshot CSV is never overwritten.
    snap_df = pd.read_csv(snap, dtype=str, keep_default_na=False)
    price_df = pd.read_csv(price, dtype=str, keep_default_na=False)
    snap_df, adjusted_prices = prepare_adjusted_label_inputs(snap_df, price_df)
    spy_path = REPO / "research_spy_sp500_10y.csv"
    if not spy_path.exists():
        raise FileNotFoundError(f"SPY market-session calendar is missing: {spy_path}")
    spy_df = pd.read_csv(spy_path, dtype=str, keep_default_na=False)
    if "Date" not in spy_df.columns:
        raise ValueError("SPY research price history must contain Date")
    price_map = build_market_aligned_adjusted_price_map(adjusted_prices, spy_df["Date"])

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
