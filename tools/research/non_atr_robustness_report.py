"""Summarize existing walk-forward OOS metrics without refreshing historical prices.

Research-only report. It aggregates the per-ticker, per-window metrics produced by
non_atr_integrated_backtest.py; it does not rerun data downloads or modify signals.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED = {
    "Ticker", "strategy", "split", "test_start", "test_end", "observations",
    "total_return", "annualized_return", "sharpe_zero_rf", "max_drawdown",
    "cost_bps_one_way",
}


def build_robustness_report(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return strategy-level and chronological-window summaries of OOS results."""
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"OOS metrics missing columns: {', '.join(sorted(missing))}")
    data = frame.copy()
    for col in ("split", "observations", "total_return", "annualized_return",
                "sharpe_zero_rf", "max_drawdown", "cost_bps_one_way"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["strategy"] = data["strategy"].astype("string").str.strip()
    data["Ticker"] = data["Ticker"].astype("string").str.strip().str.upper()
    data = data.dropna(subset=["strategy", "Ticker", "split", "total_return", "max_drawdown"])
    if data.empty:
        raise ValueError("OOS metrics contain no valid observations")
    if (data["observations"] <= 0).any():
        raise ValueError("OOS observations must be positive")
    if ((data["total_return"] <= -1) | (data["max_drawdown"] > 0)).any():
        raise ValueError("OOS returns or drawdowns are outside expected bounds")

    summaries = []
    for strategy, group in data.groupby("strategy", sort=True):
        summaries.append({
            "strategy": str(strategy),
            "oos_rows": int(len(group)),
            "unique_tickers": int(group["Ticker"].nunique()),
            "unique_windows": int(group["split"].nunique()),
            "positive_window_rate": float((group["total_return"] > 0).mean()),
            "median_oos_return": float(group["total_return"].median()),
            "p10_oos_return": float(group["total_return"].quantile(0.10)),
            "median_annualized_return": float(group["annualized_return"].median()),
            "median_sharpe": float(group["sharpe_zero_rf"].median()),
            "median_max_drawdown": float(group["max_drawdown"].median()),
            "p10_max_drawdown": float(group["max_drawdown"].quantile(0.10)),
            "cost_bps_one_way": ",".join(
                str(int(v)) if float(v).is_integer() else str(v)
                for v in sorted(group["cost_bps_one_way"].dropna().unique())
            ),
        })
    strategy_summary = pd.DataFrame(summaries)

    window_rows = []
    for (strategy, split), group in data.groupby(["strategy", "split"], sort=True):
        window_rows.append({
            "strategy": str(strategy),
            "split": int(split),
            "test_start": str(group["test_start"].min()),
            "test_end": str(group["test_end"].max()),
            "ticker_rows": int(len(group)),
            "positive_ticker_rate": float((group["total_return"] > 0).mean()),
            "median_oos_return": float(group["total_return"].median()),
            "p10_oos_return": float(group["total_return"].quantile(0.10)),
            "median_sharpe": float(group["sharpe_zero_rf"].median()),
            "median_max_drawdown": float(group["max_drawdown"].median()),
        })
    window_summary = pd.DataFrame(window_rows)
    return strategy_summary, window_summary


def render_markdown(strategy_summary: pd.DataFrame, window_summary: pd.DataFrame) -> str:
    """Render a concise report that keeps caveats attached to the numbers."""
    lines = [
        "# Non-ATR Strategy Robustness (Existing OOS Results)",
        "",
        "This report summarizes existing walk-forward out-of-sample metrics only. It does not refresh prices,",
        "retrain or optimize strategy parameters, or imply live-trading readiness.",
        "",
        "## Strategy-level summary",
        "",
        "| Strategy | OOS rows | Tickers | Positive windows | Median OOS return | 10th percentile return | Median Sharpe | Median max drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in strategy_summary.itertuples(index=False):
        lines.append(
            f"| {row.strategy} | {row.oos_rows} | {row.unique_tickers} | "
            f"{row.positive_window_rate:.1%} | {row.median_oos_return:.2%} | "
            f"{row.p10_oos_return:.2%} | {row.median_sharpe:.3f} | "
            f"{row.median_max_drawdown:.2%} |"
        )
    lines += [
        "",
        "## Calendar-window stability",
        "",
        "| Strategy | Split | Test period | Ticker rows | Positive tickers | Median return | 10th percentile return | Median max drawdown |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in window_summary.itertuples(index=False):
        lines.append(
            f"| {row.strategy} | {row.split} | {row.test_start}–{row.test_end} | "
            f"{row.ticker_rows} | {row.positive_ticker_rate:.1%} | "
            f"{row.median_oos_return:.2%} | {row.p10_oos_return:.2%} | "
            f"{row.median_max_drawdown:.2%} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "- Rows across tickers and adjacent market windows are not independent observations.",
        "- These summaries describe the current 5 bps one-way-cost run; they are not a cost-sensitivity study.",
        "- The source run had incomplete universe-wide historical coverage. Strictly screened results are a research subset, not a complete market-universe estimate.",
        "- Do not select a live strategy from median return alone; review drawdown tails, regime dependence, turnover, capacity, and paper-trading behavior.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="walk_forward_oos_metrics.csv from an existing run")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(args.input)
    strategy, windows = build_robustness_report(source)
    strategy.to_csv(output / "strategy_robustness_summary.csv", index=False)
    windows.to_csv(output / "strategy_window_stability.csv", index=False)
    (output / "strategy_robustness_report.md").write_text(
        render_markdown(strategy, windows), encoding="utf-8"
    )
    print(f"strategy_rows={len(strategy)}")
    print(f"strategy_window_rows={len(windows)}")
    print(f"report={output / 'strategy_robustness_report.md'}")


if __name__ == "__main__":
    main()
