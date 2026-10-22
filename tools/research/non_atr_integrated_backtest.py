"""Research-only CSV backtest runner for non-ATR strategy baselines.

Input CSV must contain Date, Ticker, and Adj Close columns. Only tickers with
complete valid daily rows across the requested shared date range are included.
Outputs are research artifacts only and never feed production signals/orders.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tools.research.non_atr_strategy_baselines import build_strategy_returns, summarize_returns
from tools.research.non_atr_validation import apply_turnover_costs, chronological_walk_forward_splits

STRATEGIES = {
    "momentum": ("momentum_return", "momentum_position"),
    "trend": ("trend_return", "trend_position"),
    "mean_reversion": ("mean_reversion_return", "mean_reversion_position"),
}


def load_complete_tickers(path: str | Path, *, min_rows: int = 756) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load per-ticker prices, excluding invalid, duplicate, short, or incomplete histories."""
    if min_rows < 2:
        raise ValueError("min_rows must be >= 2")
    frame = pd.read_csv(path)
    required = {"Date", "Ticker", "Adj Close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"input missing required columns: {', '.join(sorted(missing))}")
    frame = frame[list(required)].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Ticker"] = frame["Ticker"].astype("string").str.strip().str.upper()
    frame["Adj Close"] = pd.to_numeric(frame["Adj Close"], errors="coerce")
    frame = frame.dropna(subset=["Date", "Ticker", "Adj Close"])
    frame = frame[(frame["Ticker"] != "") & (frame["Adj Close"] > 0)]
    frame = frame.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")

    if frame.empty:
        return {}, pd.DataFrame(columns=["Ticker", "rows", "start_date", "end_date", "status", "reason"])

    # Enforce a shared date grid so tickers missing any date from the union are not
    # silently compared over different market regimes. This is deliberately strict.
    expected_dates = pd.DatetimeIndex(sorted(frame["Date"].unique()))
    eligible: dict[str, pd.DataFrame] = {}
    audit = []
    for ticker, group in frame.groupby("Ticker", sort=True):
        dates = pd.DatetimeIndex(group["Date"])
        complete = len(dates) == len(expected_dates) and dates.equals(expected_dates)
        enough = len(group) >= min_rows
        status = "eligible" if complete and enough else "excluded"
        reasons = []
        if not complete:
            reasons.append("incomplete_shared_date_history")
        if not enough:
            reasons.append(f"fewer_than_{min_rows}_rows")
        audit.append({
            "Ticker": str(ticker), "rows": int(len(group)),
            "start_date": group["Date"].min().date().isoformat(),
            "end_date": group["Date"].max().date().isoformat(),
            "status": status, "reason": ";".join(reasons),
        })
        if status == "eligible":
            eligible[str(ticker)] = group[["Date", "Adj Close"]].reset_index(drop=True)
    return eligible, pd.DataFrame(audit)


def run_backtest(
    input_csv: str | Path,
    output_dir: str | Path,
    *,
    min_rows: int = 756,
    one_way_cost_bps: float = 5.0,
    min_train_rows: int = 756,
    test_rows: int = 252,
) -> dict[str, int]:
    """Run fixed baselines and chronological OOS summaries on complete ticker histories."""
    if one_way_cost_bps < 0:
        raise ValueError("one_way_cost_bps cannot be negative")
    eligible, audit = load_complete_tickers(input_csv, min_rows=min_rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "ticker_eligibility_audit.csv", index=False)

    metric_rows = []
    oos_rows = []
    for ticker, prices in eligible.items():
        returns = build_strategy_returns(prices)
        splits = chronological_walk_forward_splits(
            returns["Date"], min_train_rows=min_train_rows, test_rows=test_rows
        )
        for strategy, (return_col, position_col) in STRATEGIES.items():
            gross = returns[return_col]
            costs = apply_turnover_costs(gross, returns[position_col], one_way_cost_bps=one_way_cost_bps)
            summary = summarize_returns(costs["net_return"])
            metric_rows.append({"Ticker": ticker, "strategy": strategy, "cost_bps_one_way": one_way_cost_bps,
                                "gross_total_return": summarize_returns(gross)["total_return"],
                                **summary})
            for split_number, split in enumerate(splits, start=1):
                mask = (returns["Date"] >= pd.Timestamp(split["test_start"])) & (
                    returns["Date"] <= pd.Timestamp(split["test_end"])
                )
                test_returns = costs.loc[mask, "net_return"]
                oos_rows.append({
                    "Ticker": ticker, "strategy": strategy, "split": split_number,
                    **split, **summarize_returns(test_returns),
                    "cost_bps_one_way": one_way_cost_bps,
                })

    metrics = pd.DataFrame(metric_rows)
    oos = pd.DataFrame(oos_rows)
    metrics.to_csv(output / "strategy_metrics.csv", index=False)
    oos.to_csv(output / "walk_forward_oos_metrics.csv", index=False)
    # Metadata makes empty outputs explicit instead of implying a successful backtest.
    summary = {
        "input_tickers": int(audit["Ticker"].nunique()) if not audit.empty else 0,
        "eligible_tickers": len(eligible),
        "excluded_tickers": int((audit["status"] == "excluded").sum()) if not audit.empty else 0,
        "metric_rows": len(metrics),
        "oos_rows": len(oos),
    }
    pd.Series(summary, name="value").to_csv(output / "run_summary.csv", header=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV with Date,Ticker,Adj Close")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-rows", type=int, default=756)
    parser.add_argument("--one-way-cost-bps", type=float, default=5.0)
    parser.add_argument("--min-train-rows", type=int, default=756)
    parser.add_argument("--test-rows", type=int, default=252)
    args = parser.parse_args()
    summary = run_backtest(
        args.input, args.output_dir, min_rows=args.min_rows,
        one_way_cost_bps=args.one_way_cost_bps,
        min_train_rows=args.min_train_rows, test_rows=args.test_rows,
    )
    print(pd.Series(summary).to_string())
    if summary["eligible_tickers"] == 0:
        raise SystemExit("No complete eligible tickers; inspect ticker_eligibility_audit.csv")


if __name__ == "__main__":
    main()
