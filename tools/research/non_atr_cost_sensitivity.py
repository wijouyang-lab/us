"""Compare fixed transaction-cost assumptions on the same PIT-eligible histories.

This utility reuses the existing price artifact and the backtest's point-in-time
eligibility logic. It never downloads or refreshes prices.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tools.research.non_atr_integrated_backtest import STRATEGIES, load_complete_tickers
from tools.research.non_atr_strategy_baselines import build_strategy_returns, summarize_returns
from tools.research.non_atr_validation import apply_turnover_costs, chronological_walk_forward_splits


DEFAULT_COSTS = (0.0, 5.0, 10.0, 20.0)


def analyze_cost_sensitivity(
    input_csv: str | Path,
    *,
    spy_path: str | Path,
    membership_paths: tuple[str | Path, str | Path, str | Path, str | Path],
    output_dir: str | Path,
    costs_bps: tuple[float, ...] = DEFAULT_COSTS,
    min_rows: int = 756,
    min_train_rows: int = 756,
    test_rows: int = 252,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run only local analysis across cost assumptions on PIT-eligible price histories."""
    if not costs_bps or any(cost < 0 for cost in costs_bps):
        raise ValueError("costs_bps must contain non-negative cost assumptions")
    if len(set(costs_bps)) != len(costs_bps):
        raise ValueError("cost assumptions must be unique")

    eligible, audit = load_complete_tickers(
        input_csv,
        min_rows=min_rows,
        spy_path=spy_path,
        membership_paths=membership_paths,
    )
    metric_rows: list[dict] = []
    oos_rows: list[dict] = []
    for ticker, prices in eligible.items():
        returns = build_strategy_returns(prices)
        splits = chronological_walk_forward_splits(
            returns["Date"], min_train_rows=min_train_rows, test_rows=test_rows
        )
        for strategy, (return_col, position_col) in STRATEGIES.items():
            gross = returns[return_col]
            held_positions = returns[position_col].shift(1).fillna(0.0)
            for cost_bps in costs_bps:
                costs = apply_turnover_costs(
                    gross, held_positions, one_way_cost_bps=cost_bps
                )
                summary = summarize_returns(costs["net_return"])
                turnover = float(costs["turnover"].mean() * 252) if not costs.empty else 0.0
                metric_rows.append({
                    "Ticker": ticker,
                    "strategy": strategy,
                    "cost_bps_one_way": float(cost_bps),
                    **summary,
                    "annualized_turnover": turnover,
                })
                for split_number, split in enumerate(splits, start=1):
                    mask = (returns["Date"] >= pd.Timestamp(split["test_start"])) & (
                        returns["Date"] <= pd.Timestamp(split["test_end"])
                    )
                    test_returns = costs.loc[mask, "net_return"]
                    if test_returns.empty:
                        continue
                    oos_rows.append({
                        "Ticker": ticker,
                        "strategy": strategy,
                        "split": split_number,
                        "test_start": split["test_start"],
                        "test_end": split["test_end"],
                        "cost_bps_one_way": float(cost_bps),
                        **summarize_returns(test_returns),
                    })

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "cost_sensitivity_eligibility_audit.csv", index=False)
    metrics = pd.DataFrame(metric_rows)
    oos = pd.DataFrame(oos_rows)
    metrics.to_csv(output / "cost_sensitivity_by_ticker.csv", index=False)
    oos.to_csv(output / "cost_sensitivity_oos_by_ticker_window.csv", index=False)

    if metrics.empty:
        summary = pd.DataFrame(columns=[
            "strategy", "cost_bps_one_way", "ticker_rows", "positive_ticker_share",
            "median_annualized_return", "median_max_drawdown", "median_annualized_turnover",
        ])
    else:
        summary = metrics.groupby(["strategy", "cost_bps_one_way"], sort=True).agg(
            ticker_rows=("Ticker", "size"),
            positive_ticker_share=("total_return", lambda values: float((values > 0).mean())),
            median_annualized_return=("annualized_return", "median"),
            median_max_drawdown=("max_drawdown", "median"),
            median_annualized_turnover=("annualized_turnover", "median"),
        ).reset_index()
    if oos.empty:
        oos_summary = pd.DataFrame(columns=[
            "strategy", "cost_bps_one_way", "oos_rows", "positive_window_share",
            "median_oos_return", "p10_oos_return", "median_max_drawdown",
        ])
    else:
        oos_summary = oos.groupby(["strategy", "cost_bps_one_way"], sort=True).agg(
            oos_rows=("Ticker", "size"),
            positive_window_share=("total_return", lambda values: float((values > 0).mean())),
            median_oos_return=("total_return", "median"),
            p10_oos_return=("total_return", lambda values: values.quantile(0.10)),
            median_max_drawdown=("max_drawdown", "median"),
        ).reset_index()
    summary.to_csv(output / "cost_sensitivity_summary.csv", index=False)
    oos_summary.to_csv(output / "cost_sensitivity_oos_summary.csv", index=False)
    return summary, oos_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="existing partial_prices.csv artifact")
    parser.add_argument("--spy-calendar", required=True, help="existing partial_spy.csv artifact")
    parser.add_argument("--sp500-membership", required=True)
    parser.add_argument("--ticker-aliases", required=True)
    parser.add_argument("--nasdaq100-membership", required=True)
    parser.add_argument("--dow30-membership", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--costs-bps", default="0,5,10,20")
    args = parser.parse_args()
    costs = tuple(float(value.strip()) for value in args.costs_bps.split(",") if value.strip())
    summary, oos_summary = analyze_cost_sensitivity(
        args.input,
        spy_path=args.spy_calendar,
        membership_paths=(
            args.sp500_membership,
            args.ticker_aliases,
            args.nasdaq100_membership,
            args.dow30_membership,
        ),
        output_dir=args.output_dir,
        costs_bps=costs,
    )
    print("Full-history cost sensitivity:")
    print(summary.to_string(index=False))
    print("\nWalk-forward OOS cost sensitivity:")
    print(oos_summary.to_string(index=False))


if __name__ == "__main__":
    main()
