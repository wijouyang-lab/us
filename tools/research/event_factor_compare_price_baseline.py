"""Paired comparison of event scores vs a price-only momentum baseline.

The comparison restricts both portfolios to the same ticker/decision rows with
valid event scores and sufficient pre-decision price history. Momentum uses only
price rows with a session date strictly earlier than the decision's calendar date.
This is research-only and does not connect to production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from tools.research.event_factor_backtest import evaluate


def build_paired_signals(
    signals_path: str,
    prices_path: str,
    *,
    lookback: int = 20,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if lookback < 2:
        raise ValueError("lookback must be at least 2 price observations")
    signals = pd.read_csv(signals_path, dtype={"ticker": str})
    required_s = {"decision_at", "ticker", "event_score", "coverage_status"}
    if not required_s.issubset(signals.columns):
        raise ValueError(f"signals CSV requires {sorted(required_s)}")
    signals["decision_at"] = pd.to_datetime(signals["decision_at"], errors="coerce", utc=True)
    if signals["decision_at"].isna().any():
        raise ValueError("signals contain invalid decision_at timestamps")
    signals["ticker"] = signals["ticker"].astype(str).str.strip().str.upper()
    signals["event_score"] = pd.to_numeric(signals["event_score"], errors="coerce")
    if signals.duplicated(["decision_at", "ticker"]).any():
        raise ValueError("duplicate decision_at/ticker signal rows")
    signals = signals[(signals["coverage_status"].str.lower() == "available") & signals["event_score"].notna()].copy()

    prices = pd.read_csv(prices_path, dtype={"ticker": str})
    if not {"date", "ticker", "close"}.issubset(prices.columns):
        raise ValueError("prices CSV requires date,ticker,close")
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce", utc=True)
    prices["ticker"] = prices["ticker"].astype(str).str.strip().str.upper()
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["date", "close"])
    prices = prices[prices["close"] > 0].sort_values(["ticker", "date"])
    if prices.duplicated(["ticker", "date"]).any():
        raise ValueError("duplicate ticker/date price rows")

    by_ticker = {ticker: group.reset_index(drop=True) for ticker, group in prices.groupby("ticker")}
    rows: list[dict[str, Any]] = []
    for row in signals.itertuples(index=False):
        history = by_ticker.get(row.ticker)
        if history is None:
            continue
        # The price input is daily session data. Exclude the decision date
        # entirely, even if date-only rows were parsed as midnight UTC.
        past = history[history["date"].dt.date < row.decision_at.date()]
        if len(past) < lookback:
            continue
        window = past.iloc[-lookback:]
        start, end = float(window.iloc[0]["close"]), float(window.iloc[-1]["close"])
        if start <= 0 or end <= 0:
            continue
        rows.append({
            "decision_at": row.decision_at.isoformat(),
            "ticker": row.ticker,
            "event_score": float(row.event_score),
            "momentum_score": end / start - 1.0,
            "coverage_status": "available",
        })
    paired = pd.DataFrame(rows, columns=[
        "decision_at", "ticker", "event_score", "momentum_score", "coverage_status"
    ])
    report = {
        "input_event_signal_rows": len(signals),
        "paired_rows": len(paired),
        "dropped_for_insufficient_history_or_prices": len(signals) - len(paired),
        "momentum_lookback_observations": lookback,
        "price_history_cutoff": "session date strictly before decision calendar date",
        "paired_universe": True,
        "research_only": True,
        "production_signal_generated": False,
    }
    return paired, report


def compare(
    signals_path: str,
    prices_path: str,
    *,
    lookback: int = 20,
    horizon: int = 20,
    cost_bps_per_side: float = 5.0,
    quantile: float = 0.2,
    min_names_per_side: int = 5,
) -> dict[str, Any]:
    paired, pair_report = build_paired_signals(signals_path, prices_path, lookback=lookback)
    if paired.empty:
        return {
            "status": "insufficient_data",
            "reason": "No event-covered rows have sufficient pre-decision price history.",
            "pairing": pair_report,
            "research_only": True,
            "production_signal_generated": False,
        }
    # Keep scratch files outside the input directory. This avoids write-permission
    # failures and collisions when independent comparisons run concurrently.
    with tempfile.TemporaryDirectory(prefix="event-factor-paired-") as temp_dir:
        event_path = Path(temp_dir) / "paired_event.csv"
        momentum_path = Path(temp_dir) / "paired_momentum.csv"
        event = paired[["decision_at", "ticker", "event_score", "coverage_status"]]
        momentum = paired[["decision_at", "ticker", "momentum_score", "coverage_status"]].rename(
            columns={"momentum_score": "event_score"}
        )
        event.to_csv(event_path, index=False)
        momentum.to_csv(momentum_path, index=False)
        event_result = evaluate(
            str(event_path), prices_path, horizon=horizon,
            cost_bps_per_side=cost_bps_per_side, quantile=quantile,
            min_names_per_side=min_names_per_side,
        )
        momentum_result = evaluate(
            str(momentum_path), prices_path, horizon=horizon,
            cost_bps_per_side=cost_bps_per_side, quantile=quantile,
            min_names_per_side=min_names_per_side,
        )
    return {
        "status": "evaluated" if event_result["status"] == momentum_result["status"] == "evaluated" else "insufficient_data",
        "pairing": pair_report,
        "configuration": {
            "momentum_lookback_observations": lookback,
            "forward_horizon_observations": horizon,
            "cost_bps_per_side": cost_bps_per_side,
            "quantile": quantile,
            "min_names_per_side": min_names_per_side,
        },
        "event_factor": event_result,
        "price_only_momentum_baseline": momentum_result,
        "interpretation": [
            "Both strategies use the same paired tickers at each decision time.",
            "The price-only baseline is trailing close-to-close momentum, not a production strategy.",
            "Overlapping forward returns and unadjusted Sharpe remain limitations.",
            "This comparison is exploratory; freeze choices before chronological out-of-sample evaluation.",
        ],
        "research_only": True,
        "production_signal_generated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--cost-bps-per-side", type=float, default=5.0)
    parser.add_argument("--quantile", type=float, default=0.2)
    parser.add_argument("--min-names-per-side", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare(
        args.signals, args.prices, lookback=args.lookback,
        horizon=args.horizon, cost_bps_per_side=args.cost_bps_per_side,
        quantile=args.quantile, min_names_per_side=args.min_names_per_side,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "pairing": result["pairing"],
        "event_mean_net_return_pct": result.get("event_factor", {}).get("mean_net_return_pct"),
        "momentum_mean_net_return_pct": result.get("price_only_momentum_baseline", {}).get("mean_net_return_pct"),
        "research_only": True,
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
