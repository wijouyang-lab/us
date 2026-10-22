"""Research-only CSV backtest runner for non-ATR strategy baselines.

Input CSV must contain Date, Ticker, and Adj Close columns. When --sessions is
provided, each ticker is checked against market sessions within its own observed
date span, avoiding the erroneous requirement that every ticker share identical
IPO/listing history. Outputs never feed production signals/orders.
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


def load_complete_tickers(
    path: str | Path, *, min_rows: int = 756, sessions_path: str | Path | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load valid ticker histories and audit missing expected sessions within each ticker's span."""
    if min_rows < 2:
        raise ValueError("min_rows must be >= 2")
    frame = pd.read_csv(path)
    required = {"Date", "Ticker", "Adj Close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"input missing required columns: {', '.join(sorted(missing))}")
    frame = frame[["Date", "Ticker", "Adj Close"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
    frame["Ticker"] = frame["Ticker"].astype("string").str.strip().str.upper()
    frame["Adj Close"] = pd.to_numeric(frame["Adj Close"], errors="coerce")
    frame = frame.dropna(subset=["Date", "Ticker", "Adj Close"])
    frame = frame[(frame["Ticker"] != "") & (frame["Adj Close"] > 0)]
    frame = frame.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    if frame.empty:
        return {}, pd.DataFrame(columns=["Ticker", "rows", "start_date", "end_date", "expected_sessions", "missing_sessions", "status", "reason"])

    market_sessions = None
    if sessions_path is not None:
        session_frame = pd.read_csv(sessions_path)
        if "Date" not in session_frame:
            raise ValueError("sessions CSV must contain a Date column (e.g. SPY price history)")
        market_sessions = pd.DatetimeIndex(pd.to_datetime(session_frame["Date"], errors="coerce").dropna().dt.normalize().unique()).sort_values()
        if market_sessions.empty:
            raise ValueError("sessions CSV contains no valid dates")

    eligible: dict[str, pd.DataFrame] = {}
    audit = []
    for ticker, group in frame.groupby("Ticker", sort=True):
        dates = pd.DatetimeIndex(group["Date"])
        if market_sessions is None:
            expected = dates
            missing_dates = pd.DatetimeIndex([])
            complete = True
            coverage_basis = "observed_span_only_no_sessions_calendar"
        else:
            expected = market_sessions[(market_sessions >= dates.min()) & (market_sessions <= dates.max())]
            missing_dates = expected.difference(dates)
            complete = len(expected) > 0 and len(missing_dates) == 0
            coverage_basis = "market_sessions_within_observed_span"
        enough = len(group) >= min_rows
        reasons = []
        if not complete:
            reasons.append("missing_expected_market_sessions" if market_sessions is not None else "no_expected_sessions")
        if not enough:
            reasons.append(f"fewer_than_{min_rows}_rows")
        status = "eligible" if complete and enough else "excluded"
        audit.append({
            "Ticker": str(ticker), "rows": int(len(group)),
            "start_date": dates.min().date().isoformat(), "end_date": dates.max().date().isoformat(),
            "expected_sessions": int(len(expected)), "missing_sessions": int(len(missing_dates)),
            "coverage_basis": coverage_basis, "status": status, "reason": ";".join(reasons),
        })
        if status == "eligible":
            eligible[str(ticker)] = group[["Date", "Adj Close"]].reset_index(drop=True)
    return eligible, pd.DataFrame(audit)


def run_backtest(
    input_csv: str | Path, output_dir: str | Path, *, min_rows: int = 756,
    one_way_cost_bps: float = 5.0, min_train_rows: int = 756,
    test_rows: int = 252, sessions_path: str | Path | None = None,
) -> dict[str, int]:
    """Run fixed baselines and chronological OOS summaries on audited ticker histories."""
    if one_way_cost_bps < 0:
        raise ValueError("one_way_cost_bps cannot be negative")
    eligible, audit = load_complete_tickers(input_csv, min_rows=min_rows, sessions_path=sessions_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "ticker_eligibility_audit.csv", index=False)
    metric_rows, oos_rows = [], []
    for ticker, prices in eligible.items():
        returns = build_strategy_returns(prices)
        splits = chronological_walk_forward_splits(returns["Date"], min_train_rows=min_train_rows, test_rows=test_rows)
        for strategy, (return_col, position_col) in STRATEGIES.items():
            gross = returns[return_col]
            held_positions = returns[position_col].shift(1).fillna(0.0)
            costs = apply_turnover_costs(gross, held_positions, one_way_cost_bps=one_way_cost_bps)
            metric_rows.append({"Ticker": ticker, "strategy": strategy, "cost_bps_one_way": one_way_cost_bps,
                                "gross_total_return": summarize_returns(gross)["total_return"],
                                **summarize_returns(costs["net_return"])})
            for split_number, split in enumerate(splits, start=1):
                mask = returns["Date"].between(pd.Timestamp(split["test_start"]), pd.Timestamp(split["test_end"]))
                oos_rows.append({"Ticker": ticker, "strategy": strategy, "split": split_number, **split,
                                 **summarize_returns(costs.loc[mask, "net_return"]),
                                 "cost_bps_one_way": one_way_cost_bps})
    metrics, oos = pd.DataFrame(metric_rows), pd.DataFrame(oos_rows)
    metrics.to_csv(output / "strategy_metrics.csv", index=False)
    oos.to_csv(output / "walk_forward_oos_metrics.csv", index=False)
    summary = {"input_tickers": int(audit["Ticker"].nunique()) if not audit.empty else 0,
               "eligible_tickers": len(eligible),
               "excluded_tickers": int((audit["status"] == "excluded").sum()) if not audit.empty else 0,
               "metric_rows": len(metrics), "oos_rows": len(oos)}
    pd.Series(summary, name="value").to_csv(output / "run_summary.csv", header=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV with Date,Ticker,Adj Close")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sessions", help="Optional SPY/session CSV; checks missing sessions within each ticker's observed span")
    parser.add_argument("--min-rows", type=int, default=756)
    parser.add_argument("--one-way-cost-bps", type=float, default=5.0)
    parser.add_argument("--min-train-rows", type=int, default=756)
    parser.add_argument("--test-rows", type=int, default=252)
    args = parser.parse_args()
    summary = run_backtest(args.input, args.output_dir, min_rows=args.min_rows,
                           one_way_cost_bps=args.one_way_cost_bps, min_train_rows=args.min_train_rows,
                           test_rows=args.test_rows, sessions_path=args.sessions)
    print(pd.Series(summary).to_string())
    if summary["eligible_tickers"] == 0:
        raise SystemExit("No complete eligible tickers; inspect ticker_eligibility_audit.csv")


if __name__ == "__main__":
    main()
