#!/usr/bin/env python3
"""Ex-post volatility-matched, monthly rebalanced passive QQQ/BIL controls.

The input is pinned to PR #438's daily NAV and adjusted ETF price histories.
This is a historical diagnostic, not an investable signal or an independent
out-of-sample test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

INITIAL_CAPITAL = 50_000.0
COST_BPS = 10.0
TRADING_DAYS = 252
CONFIGS = {
    "w25_c10_all_legs": "transition_w25",
    "w50_c10_all_legs": "transition_w50",
    "w100_c10_all_legs": "transition_w100",
}
REQUIRED = [
    "date", "transition_w25", "transition_w50", "transition_w100",
    "qqq_adj_open", "qqq_adj_close", "bil_adj_open", "bil_adj_close",
]


class DataValidationError(ValueError):
    """Raised when a source series cannot support a complete risk comparison."""


def load_input(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        raise DataValidationError(f"missing columns: {missing}")
    frame = frame[REQUIRED].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        raise DataValidationError("invalid date")
    if frame["date"].duplicated().any():
        raise DataValidationError("duplicate dates")
    if not frame["date"].is_monotonic_increasing:
        raise DataValidationError("dates must be strictly increasing")
    numeric = [column for column in REQUIRED if column != "date"]
    values = frame[numeric].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise DataValidationError("NaN or infinite values")
    if (frame[numeric] <= 0).any().any():
        raise DataValidationError("NAV and adjusted prices must be positive")
    return frame.reset_index(drop=True)


def _metrics(dates: pd.Series, values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    dates = pd.DatetimeIndex(dates)
    if len(values) != len(dates) or len(values) < 3:
        raise DataValidationError("at least three aligned daily observations required")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise DataValidationError("NAV contains non-finite or non-positive values")

    returns = values[1:] / values[:-1] - 1.0
    volatility = float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS))
    annual_mean = float(np.mean(returns) * TRADING_DAYS)
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-12)
    cagr = float((values[-1] / values[0]) ** (1.0 / years) - 1.0)

    running_peak = values[0]
    running_peak_idx = 0
    max_drawdown = 0.0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    longest_underwater = 0
    current_underwater = 0
    for index, value in enumerate(values):
        if value >= running_peak:
            running_peak = value
            running_peak_idx = index
        drawdown = value / running_peak - 1.0
        if drawdown < max_drawdown:
            max_drawdown = float(drawdown)
            max_dd_peak_idx = running_peak_idx
            max_dd_trough_idx = index
        if value < running_peak:
            current_underwater += 1
            longest_underwater = max(longest_underwater, current_underwater)
        else:
            current_underwater = 0

    recovery_idx = None
    peak_value = values[max_dd_peak_idx]
    for index in range(max_dd_trough_idx + 1, len(values)):
        if values[index] >= peak_value:
            recovery_idx = index
            break

    return {
        "start": dates[0].date().isoformat(),
        "end": dates[-1].date().isoformat(),
        "observations": int(len(values)),
        "final_multiple": float(values[-1] / values[0]),
        "final_nav_usd": float(INITIAL_CAPITAL * values[-1] / values[0]),
        "cagr": cagr,
        "volatility": volatility,
        "sharpe_rf0": float(annual_mean / volatility) if volatility > 0 else None,
        "max_drawdown": float(max_drawdown),
        "max_drawdown_peak_date": dates[max_dd_peak_idx].date().isoformat(),
        "max_drawdown_trough_date": dates[max_dd_trough_idx].date().isoformat(),
        "max_drawdown_recovery_date": (
            dates[recovery_idx].date().isoformat() if recovery_idx is not None else None
        ),
        "longest_underwater_sessions": int(longest_underwater),
    }


def simulate_monthly_passive(
    frame: pd.DataFrame, qqq_weight: float, cost_bps: float = COST_BPS
) -> tuple[np.ndarray, dict]:
    """Buy a QQQ/BIL mix, then restore weights at next month's first session Open.

    Adjusted Open/Close prices are used because PR #438's transition backtest
    uses AdjOpen/AdjClose. Dividends are therefore embedded in the adjusted
    price series (not separately credited as cash). Initial positions are not
    charged, matching PR #438's uncharged initial BIL reserve convention;
    all subsequent rebalance order legs pay the same proportional bps cost.
    """
    if not 0.0 < qqq_weight < 1.0:
        raise ValueError("qqq_weight must be between 0 and 1")
    rate = float(cost_bps) / 10_000.0
    dates = pd.DatetimeIndex(frame["date"])
    q_open = frame["qqq_adj_open"].to_numpy(dtype=float)
    q_close = frame["qqq_adj_close"].to_numpy(dtype=float)
    b_open = frame["bil_adj_open"].to_numpy(dtype=float)
    b_close = frame["bil_adj_close"].to_numpy(dtype=float)

    # Initial allocation on the first session's adjusted Open.
    q_shares = qqq_weight / q_open[0]
    b_shares = (1.0 - qqq_weight) / b_open[0]
    cash = 0.0
    first_nav = q_shares * q_close[0] + b_shares * b_close[0]
    scale = 1.0 / first_nav
    q_shares *= scale
    b_shares *= scale
    nav = [1.0]

    # The last session of each month sets the target; the next session executes.
    rebalance_indices = {
        index
        for index in range(1, len(dates))
        if dates[index].month != dates[index - 1].month
        or dates[index].year != dates[index - 1].year
    }
    total_cost = 0.0
    total_notional = 0.0
    order_legs = 0
    buy_legs = 0
    sell_legs = 0

    for index in range(1, len(dates)):
        if index in rebalance_indices:
            open_prices = {"QQQ": q_open[index], "BIL": b_open[index]}
            nav_open = cash + q_shares * q_open[index] + b_shares * b_open[index]
            desired = {
                "QQQ": nav_open * qqq_weight / open_prices["QQQ"],
                "BIL": nav_open * (1.0 - qqq_weight) / open_prices["BIL"],
            }
            current = {"QQQ": q_shares, "BIL": b_shares}
            deltas = {ticker: desired[ticker] - current[ticker] for ticker in current}

            # Sell first so proceeds fund the buys; no margin is assumed.
            for ticker, delta in deltas.items():
                if delta < -1e-12:
                    notional = -delta * open_prices[ticker]
                    fee = notional * rate
                    cash += notional - fee
                    if ticker == "QQQ":
                        q_shares += delta
                    else:
                        b_shares += delta
                    total_cost += fee
                    total_notional += notional
                    order_legs += 1
                    sell_legs += 1

            for ticker, delta in deltas.items():
                if delta > 1e-12:
                    price = open_prices[ticker]
                    affordable = max(cash, 0.0) / (price * (1.0 + rate))
                    quantity = min(delta, affordable)
                    if quantity > 1e-12:
                        notional = quantity * price
                        fee = notional * rate
                        cash -= notional + fee
                        if ticker == "QQQ":
                            q_shares += quantity
                        else:
                            b_shares += quantity
                        total_cost += fee
                        total_notional += notional
                        order_legs += 1
                        buy_legs += 1

        nav.append(cash + q_shares * q_close[index] + b_shares * b_close[index])

    diagnostics = {
        "rebalance_sessions": int(len(rebalance_indices)),
        "order_legs": int(order_legs),
        "buy_legs": int(buy_legs),
        "sell_legs": int(sell_legs),
        "total_traded_notional_initial_equity_multiple": float(total_notional),
        "total_cost_initial_equity_multiple": float(total_cost),
        "total_traded_notional_usd": float(total_notional * INITIAL_CAPITAL),
        "total_cost_usd": float(total_cost * INITIAL_CAPITAL),
        "qqq_weight": float(qqq_weight),
        "bil_weight": float(1.0 - qqq_weight),
        "cost_bps_per_leg": float(cost_bps),
    }
    return np.asarray(nav, dtype=float), diagnostics


def match_volatility(
    frame: pd.DataFrame, target_volatility: float, cost_bps: float = COST_BPS
) -> tuple[float, np.ndarray, dict]:
    """Find the in-sample QQQ starting weight whose passive mix matches target vol."""
    low, high = 0.0, 1.0
    low_vol = _metrics(frame["date"], simulate_monthly_passive(frame, 1e-9, cost_bps)[0])[
        "volatility"
    ]
    high_vol = _metrics(frame["date"], simulate_monthly_passive(frame, 1.0 - 1e-9, cost_bps)[0])[
        "volatility"
    ]
    if not low_vol <= target_volatility <= high_vol:
        raise DataValidationError(
            f"target volatility {target_volatility:.8f} is outside "
            f"passive mix range [{low_vol:.8f}, {high_vol:.8f}]"
        )

    best_nav = None
    best_diagnostics = None
    for _ in range(70):
        midpoint = (low + high) / 2.0
        nav, diagnostics = simulate_monthly_passive(frame, midpoint, cost_bps)
        observed = _metrics(frame["date"], nav)["volatility"]
        best_nav, best_diagnostics = nav, diagnostics
        if observed < target_volatility:
            low = midpoint
        else:
            high = midpoint

    weight = (low + high) / 2.0
    best_nav, best_diagnostics = simulate_monthly_passive(frame, weight, cost_bps)
    observed = _metrics(frame["date"], best_nav)["volatility"]
    if abs(observed - target_volatility) > 1e-8:
        raise DataValidationError("volatility match did not converge")
    best_diagnostics["matched_volatility"] = float(observed)
    best_diagnostics["target_volatility"] = float(target_volatility)
    best_diagnostics["absolute_volatility_error"] = float(abs(observed - target_volatility))
    return float(weight), best_nav, best_diagnostics


def analyze(frame: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    dates = frame["date"]
    results = {
        "title": "QQQ Transition vs ex-post volatility-matched passive QQQ/BIL",
        "period": {
            "start": dates.iloc[0].date().isoformat(),
            "end": dates.iloc[-1].date().isoformat(),
            "sessions": int(len(frame)),
        },
        "method": {
            "transition_configs": list(CONFIGS.keys()),
            "passive_rule": (
                "Initial QQQ/BIL mix; month-end weights are restored at the next "
                "session's adjusted Open; no forecast or regime signal."
            ),
            "risk_match": "Full-sample annualized daily volatility, sample std (ddof=1) * sqrt(252).",
            "execution_prices": "AdjOpen for trades and AdjClose for marks, matching PR #438.",
            "dividends": "Embedded in adjusted prices; not separately credited as cash.",
            "passive_costs": (
                "10 bps per executed rebalance order leg; initial buys are uncharged "
                "to match PR #438's initial BIL reserve convention."
            ),
            "initial_capital_usd": INITIAL_CAPITAL,
            "important_caveat": (
                "The matched QQQ weight is selected using the entire historical sample. "
                "This is an ex-post diagnostic, not a pre-registered or deployable weight."
            ),
        },
        "comparisons": {},
    }
    daily = pd.DataFrame({"date": dates.dt.date.astype(str)})
    stage_ranges = [
        ("2007-2015", "2007-05-30", "2015-12-31"),
        ("2016-2020", "2016-01-01", "2020-12-31"),
        ("2021-2026", "2021-01-01", "2026-10-30"),
    ]

    for source_config, column in CONFIGS.items():
        strategy_nav = frame[column].to_numpy(dtype=float)
        strategy_metrics = _metrics(dates, strategy_nav)
        weight, passive_nav, diagnostics = match_volatility(
            frame, strategy_metrics["volatility"], COST_BPS
        )
        passive_metrics = _metrics(dates, passive_nav)
        stage_metrics = {}
        for stage_name, start, end in stage_ranges:
            mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
            indices = np.flatnonzero(mask.to_numpy())
            if len(indices) < 3:
                stage_metrics[stage_name] = {"status": "INSUFFICIENT"}
                continue
            first, last = int(indices[0]), int(indices[-1])
            stage_metrics[stage_name] = {
                "transition": _metrics(dates.iloc[first:last + 1], strategy_nav[first:last + 1]),
                "passive": _metrics(dates.iloc[first:last + 1], passive_nav[first:last + 1]),
            }

        results["comparisons"][source_config] = {
            "strategy": strategy_metrics,
            "passive": passive_metrics,
            "passive_diagnostics": diagnostics,
            "differences": {
                "cagr_passive_minus_transition_pp": float(
                    (passive_metrics["cagr"] - strategy_metrics["cagr"]) * 100.0
                ),
                "max_drawdown_passive_minus_transition_pp": float(
                    (passive_metrics["max_drawdown"] - strategy_metrics["max_drawdown"]) * 100.0
                ),
                "sharpe_passive_minus_transition": float(
                    passive_metrics["sharpe_rf0"] - strategy_metrics["sharpe_rf0"]
                ),
                "final_nav_passive_minus_transition_usd": float(
                    passive_metrics["final_nav_usd"] - strategy_metrics["final_nav_usd"]
                ),
            },
            "stages": stage_metrics,
        }
        suffix = source_config.replace("w", "w").replace("_c10_all_legs", "")
        daily[f"transition_{suffix}"] = strategy_nav
        daily[f"passive_{suffix}"] = passive_nav

    return results, daily


def run(input_path: Path, output_dir: Path) -> dict:
    frame = load_input(input_path)
    results, daily = analyze(frame)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    daily.to_csv(output_dir / "daily_nav.csv", index=False, float_format="%.12g")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = run(args.input, args.output)
    print(json.dumps(results["comparisons"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
