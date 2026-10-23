"""Portfolio-level simulation using existing point-in-time eligible adjusted-price histories.

This is research-only. It never downloads or refreshes prices. Portfolio weights are
equal-weighted across eligible PIT members with signals, with unallocated capital
held in cash. Costs are charged on portfolio weight changes, including entry/exit
and reweighting as the eligible PIT universe changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tools.research.non_atr_integrated_backtest import STRATEGIES, load_complete_tickers
from tools.research.non_atr_strategy_baselines import build_strategy_returns, summarize_returns
from tools.research.non_atr_validation import chronological_walk_forward_splits


def combine_equal_weight_portfolio(
    ticker_daily: pd.DataFrame,
    calendar: pd.Series | pd.DatetimeIndex,
    *,
    one_way_cost_bps: float,
) -> pd.DataFrame:
    """Combine long ticker/day rows into a cash-aware, equal-weight portfolio.

    Required columns: Date, Ticker, daily_return, held_position. The held position
    must already be lagged one session relative to the close-to-close return.
    Missing ticker dates mean that ticker is not a PIT member on that session.
    """
    if one_way_cost_bps < 0:
        raise ValueError("one_way_cost_bps cannot be negative")
    required = {"Date", "Ticker", "daily_return", "held_position"}
    missing = required - set(ticker_daily.columns)
    if missing:
        raise ValueError(f"ticker_daily missing columns: {', '.join(sorted(missing))}")
    data = ticker_daily[list(required)].copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce").dt.normalize()
    data["Ticker"] = data["Ticker"].astype("string").str.strip().str.upper()
    data["daily_return"] = pd.to_numeric(data["daily_return"], errors="coerce")
    data["held_position"] = pd.to_numeric(data["held_position"], errors="coerce")
    data = data.dropna(subset=["Date", "Ticker", "daily_return", "held_position"])
    data = data.drop_duplicates(["Date", "Ticker"], keep="last")
    if data.empty:
        raise ValueError("ticker_daily contains no valid rows")
    if not data["held_position"].between(0, 1).all():
        raise ValueError("held_position must be between 0 and 1")
    if (data["daily_return"] <= -1).any():
        raise ValueError("daily_return must be greater than -100%")

    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(calendar), errors="coerce").dropna().dt.normalize().unique()).sort_values()
    if dates.empty:
        raise ValueError("calendar contains no valid dates")
    data = data[data["Date"].isin(dates)]
    if data.empty:
        raise ValueError("ticker_daily has no rows on the supplied calendar")

    active_counts = data.groupby("Date")["Ticker"].nunique().reindex(dates).fillna(0)
    data["active_count"] = data["Date"].map(active_counts).astype(float)
    data["weight"] = data["held_position"] / data["active_count"].where(data["active_count"] > 0)
    data["weight"] = data["weight"].fillna(0.0)

    weight_panel = data.pivot(index="Date", columns="Ticker", values="weight").reindex(dates).fillna(0.0)
    return_panel = data.pivot(index="Date", columns="Ticker", values="daily_return").reindex(dates).fillna(0.0)
    weight_change = weight_panel.diff().fillna(weight_panel).abs()
    turnover = weight_change.sum(axis=1)
    gross_return = (weight_panel * return_panel).sum(axis=1)
    cost = turnover * (one_way_cost_bps / 10000.0)
    net_return = (1.0 + gross_return) * (1.0 - cost) - 1.0
    return pd.DataFrame({
        "gross_return": gross_return,
        "turnover": turnover,
        "cost": cost,
        "net_return": net_return,
        "exposure": weight_panel.sum(axis=1),
        "active_tickers": active_counts.astype(int),
    }, index=dates).rename_axis("Date")


def _read_spy_calendar(path: str | Path) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    spy = pd.read_csv(path)
    required = {"Date", "Adj Close"}
    missing = required - set(spy.columns)
    if missing:
        raise ValueError(f"SPY calendar missing columns: {', '.join(sorted(missing))}")
    spy["Date"] = pd.to_datetime(spy["Date"], errors="coerce").dt.normalize()
    spy["Adj Close"] = pd.to_numeric(spy["Adj Close"], errors="coerce")
    spy = spy.dropna(subset=["Date", "Adj Close"])
    spy = spy[spy["Adj Close"] > 0].sort_values("Date").drop_duplicates("Date", keep="last")
    if spy.empty:
        raise ValueError("SPY calendar contains no valid positive adjusted prices")
    spy["benchmark_return"] = spy["Adj Close"].pct_change().fillna(0.0)
    return spy, pd.DatetimeIndex(spy["Date"])


def _make_ticker_daily(eligible: dict[str, pd.DataFrame], strategy: str) -> pd.DataFrame:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    _, position_col = STRATEGIES[strategy]
    pieces = []
    for ticker, prices in eligible.items():
        returns = build_strategy_returns(prices)
        pieces.append(pd.DataFrame({
            "Date": returns["Date"],
            "Ticker": ticker,
            "daily_return": returns["buy_and_hold_return"],
            "held_position": returns[position_col].shift(1).fillna(0.0),
        }))
    if not pieces:
        return pd.DataFrame(columns=["Date", "Ticker", "daily_return", "held_position"])
    return pd.concat(pieces, ignore_index=True)


def run_portfolio_simulation(
    input_csv: str | Path,
    spy_path: str | Path,
    membership_paths: tuple[str | Path, str | Path, str | Path, str | Path],
    output_dir: str | Path,
    *,
    costs_bps: tuple[float, ...] = (0.0, 5.0, 10.0, 20.0),
    min_rows: int = 756,
    min_train_rows: int = 756,
    test_rows: int = 252,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run a synchronized portfolio simulation over the existing price inputs."""
    if not costs_bps or any(cost < 0 for cost in costs_bps) or len(set(costs_bps)) != len(costs_bps):
        raise ValueError("costs_bps must be unique, non-negative values")
    eligible, audit = load_complete_tickers(
        input_csv, min_rows=min_rows, spy_path=spy_path, membership_paths=membership_paths
    )
    spy, calendar = _read_spy_calendar(spy_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "portfolio_eligibility_audit.csv", index=False)

    full_rows = []
    oos_rows = []
    annual_rows = []
    splits = chronological_walk_forward_splits(
        pd.Series(calendar), min_train_rows=min_train_rows, test_rows=test_rows
    )
    for strategy in STRATEGIES:
        ticker_daily = _make_ticker_daily(eligible, strategy)
        if ticker_daily.empty:
            continue
        for cost_bps in costs_bps:
            portfolio = combine_equal_weight_portfolio(
                ticker_daily, calendar, one_way_cost_bps=cost_bps
            )
            benchmark = spy.set_index("Date")["benchmark_return"].reindex(portfolio.index).fillna(0.0)
            stats = summarize_returns(portfolio["net_return"])
            benchmark_stats = summarize_returns(benchmark)
            full_rows.append({
                "strategy": strategy,
                "cost_bps_one_way": float(cost_bps),
                **stats,
                "benchmark_total_return": benchmark_stats["total_return"],
                "benchmark_annualized_return": benchmark_stats["annualized_return"],
                "benchmark_sharpe_zero_rf": benchmark_stats["sharpe_zero_rf"],
                "mean_exposure": float(portfolio["exposure"].mean()),
                "max_exposure": float(portfolio["exposure"].max()),
                "annualized_turnover": float(portfolio["turnover"].mean() * 252),
                "worst_calendar_year_return": float(
                    (1.0 + portfolio["net_return"]).groupby(portfolio.index.year).prod().sub(1.0).min()
                ),
            })
            for year, group in portfolio["net_return"].groupby(portfolio.index.year):
                annual_rows.append({
                    "strategy": strategy, "cost_bps_one_way": float(cost_bps),
                    "year": int(year), **summarize_returns(group),
                })
            for split_number, split in enumerate(splits, start=1):
                mask = (portfolio.index >= pd.Timestamp(split["test_start"])) & (
                    portfolio.index <= pd.Timestamp(split["test_end"])
                )
                test = portfolio.loc[mask, "net_return"]
                benchmark_test = benchmark.loc[mask]
                if test.empty:
                    continue
                oos_rows.append({
                    "strategy": strategy,
                    "cost_bps_one_way": float(cost_bps),
                    "split": split_number,
                    "test_start": split["test_start"],
                    "test_end": split["test_end"],
                    **summarize_returns(test),
                    "benchmark_total_return": summarize_returns(benchmark_test)["total_return"],
                    "mean_exposure": float(portfolio.loc[mask, "exposure"].mean()),
                    "annualized_turnover": float(portfolio.loc[mask, "turnover"].mean() * 252),
                })

    summary = pd.DataFrame(full_rows)
    oos_summary = pd.DataFrame(oos_rows)
    annual = pd.DataFrame(annual_rows)
    summary.to_csv(output / "portfolio_strategy_summary.csv", index=False)
    oos_summary.to_csv(output / "portfolio_oos_by_window.csv", index=False)
    annual.to_csv(output / "portfolio_annual_returns.csv", index=False)
    return summary, oos_summary, annual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="existing partial_prices.csv")
    parser.add_argument("--spy-calendar", required=True, help="existing partial_spy.csv")
    parser.add_argument("--sp500-membership", required=True)
    parser.add_argument("--ticker-aliases", required=True)
    parser.add_argument("--nasdaq100-membership", required=True)
    parser.add_argument("--dow30-membership", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--costs-bps", default="0,5,10,20")
    args = parser.parse_args()
    costs = tuple(float(value.strip()) for value in args.costs_bps.split(",") if value.strip())
    summary, oos, annual = run_portfolio_simulation(
        args.input, args.spy_calendar,
        (args.sp500_membership, args.ticker_aliases, args.nasdaq100_membership, args.dow30_membership),
        args.output_dir, costs_bps=costs,
    )
    print("Portfolio-level strategy summary:")
    print(summary.to_string(index=False))
    print("\nWalk-forward OOS portfolio windows:")
    print(oos.to_string(index=False))
    print("\nCalendar-year returns:")
    print(annual.to_string(index=False))


if __name__ == "__main__":
    main()
