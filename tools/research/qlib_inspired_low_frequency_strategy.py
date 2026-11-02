#!/usr/bin/env python3
"""Qlib-inspired, price-only low-frequency strategy candidate.

Research only. Current-universe data may be survivorship-biased and is NOT PIT.
The composite is a fixed, pre-registered rank blend; no weights are fitted on
the test period. Signal is formed at month-end close, entered at next open,
and exited at the open 20 sessions after entry. Results are not deployable
alpha and do not change production strategy logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HORIZON = 20
COST_BPS = 5.0
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 5_000_000.0
MIN_NAMES = 80
TOP_FRACTION = 0.20
TEST_START = "2023-01-01"

FEATURES = ("Mom12_1", "Trend100", "LowVol60", "Reversal5", "DollarVolumeTrend")
WEIGHTS = {
    "Mom12_1": 0.35,
    "Trend100": 0.25,
    "LowVol60": 0.20,
    "Reversal5": 0.10,
    "DollarVolumeTrend": 0.10,
}
LABEL = "RESEARCH ONLY | CURRENT-UNIVERSE / SURVIVORSHIP RISK | NOT PIT | NOT DEPLOYABLE"


def load_panel(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Date", "Ticker", "Open", "Close"])
    df = df[(df["Open"] > 0) & (df["Close"] > 0)].copy()
    df = df.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    g = df.groupby("Ticker", sort=False)

    daily_ret = g["Close"].pct_change()
    df["Mom12_1"] = g["Close"].transform(lambda s: s.shift(21) / s.shift(252) - 1)
    df["Trend100"] = g["Close"].transform(lambda s: s / s.rolling(100, min_periods=100).mean() - 1)
    df["LowVol60"] = -daily_ret.groupby(df["Ticker"]).transform(
        lambda s: s.rolling(60, min_periods=60).std() * np.sqrt(252)
    )
    df["Reversal5"] = -g["Close"].transform(lambda s: s / s.shift(5) - 1)
    dollar_volume = df["Close"] * df["Volume"]
    dv20 = dollar_volume.groupby(df["Ticker"]).transform(lambda s: s.rolling(20, min_periods=20).mean())
    dv60 = dollar_volume.groupby(df["Ticker"]).transform(lambda s: s.rolling(60, min_periods=60).mean())
    df["DV20"] = dv20
    df["DollarVolumeTrend"] = dv20 / dv60 - 1
    # Signal at close t; enter at open t+1; exit at open t+1+HORIZON.
    df["EntryOpen"] = g["Open"].shift(-1)
    df["ExitOpen"] = g["Open"].shift(-(1 + HORIZON))
    df["Fwd20"] = df["ExitOpen"] / df["EntryOpen"] - 1
    return df


def month_ends(df: pd.DataFrame) -> list[pd.Timestamp]:
    dates = pd.Series(pd.to_datetime(df["Date"]).dropna().unique())
    if dates.empty:
        return []
    return sorted(dates.groupby(dates.dt.to_period("M")).max().tolist())


def rank_composite(frame: pd.DataFrame, weights: dict[str, float] = WEIGHTS) -> pd.Series:
    """Cross-sectional rank blend. Higher scores are preferred."""
    ranks = pd.DataFrame(index=frame.index)
    for name in FEATURES:
        ranks[name] = frame[name].rank(pct=True, method="average")
    score = sum(ranks[name] * weight for name, weight in weights.items())
    return score


def _portfolio_return(
    frame: pd.DataFrame, selected: set[str], previous: set[str], cost_bps: float
) -> dict | None:
    # Do not silently drop selected names with unavailable forward labels.
    picked = frame[frame["Ticker"].isin(selected)]
    if len(picked) != len(selected) or picked["Fwd20"].isna().any():
        return None
    turnover = 1.0 if not previous else len(selected - previous) / max(len(selected), 1)
    gross = float(picked["Fwd20"].mean())
    cost = cost_bps / 10000.0 * turnover
    return {"gross": gross, "turnover": turnover, "cost": cost, "net": gross - cost}


def evaluate(
    df: pd.DataFrame,
    dates: list[pd.Timestamp],
    cost_bps: float = COST_BPS,
    test_start: str = TEST_START,
    weights: dict[str, float] = WEIGHTS,
) -> dict:
    previous_strategy: set[str] = set()
    previous_benchmark: set[str] = set()
    rows: list[dict] = []
    start = pd.Timestamp(test_start)
    for date in dates:
        if pd.Timestamp(date) < start:
            continue
        day = df[df["Date"].eq(date)].copy()
        eligible = day[
            (day["Close"] >= MIN_PRICE) & (day["DV20"] >= MIN_DOLLAR_VOLUME)
        ].dropna(subset=list(FEATURES))
        if len(eligible) < MIN_NAMES:
            continue
        eligible["Score"] = rank_composite(eligible, weights)
        eligible = eligible.sort_values(["Score", "Ticker"], ascending=[False, True])
        count = max(1, int(np.floor(len(eligible) * TOP_FRACTION)))
        selected = set(eligible.head(count)["Ticker"])
        strat = _portfolio_return(eligible, selected, previous_strategy, cost_bps)
        # Same eligible universe and forward horizon; benchmark is equal-weight.
        benchmark_names = set(eligible["Ticker"])
        bench = _portfolio_return(eligible, benchmark_names, previous_benchmark, cost_bps)
        if strat is None or bench is None:
            # Missing forward prices for any selected name invalidates this date;
            # never silently shrink the portfolio using future data availability.
            continue
        rows.append({
            "date": pd.Timestamp(date).date().isoformat(),
            "eligible": len(eligible),
            "selected": count,
            "strategy_gross": strat["gross"],
            "strategy_turnover": strat["turnover"],
            "strategy_cost": strat["cost"],
            "strategy_net": strat["net"],
            "benchmark_gross": bench["gross"],
            "benchmark_turnover": bench["turnover"],
            "benchmark_cost": bench["cost"],
            "benchmark_net": bench["net"],
            "excess_net": strat["net"] - bench["net"],
        })
        previous_strategy, previous_benchmark = selected, benchmark_names
    return {"rows": rows, "metrics": summarize(rows)}


def summarize(rows: list[dict]) -> dict:
    if len(rows) < 3:
        return {"status": "INSUFFICIENT_DATA", "observations": len(rows)}
    frame = pd.DataFrame(rows)

    def stats_for(column: str) -> dict:
        returns = frame[column].astype(float).to_numpy()
        equity = np.cumprod(1.0 + returns)
        volatility = float(np.std(returns, ddof=1) * np.sqrt(12))
        annualized = float(np.prod(1.0 + returns) ** (12.0 / len(returns)) - 1.0)
        return {
            "observations": len(returns),
            "mean_monthly": float(np.mean(returns)),
            "annualized_return": annualized,
            "annualized_volatility": volatility,
            "sharpe": annualized / volatility if volatility > 0 else None,
            "max_drawdown": float((equity / np.maximum.accumulate(equity) - 1.0).min()),
            "positive_month_fraction": float(np.mean(returns > 0)),
        }

    return {
        "status": "DESCRIPTIVE_ONLY",
        "strategy": stats_for("strategy_net"),
        "benchmark": stats_for("benchmark_net"),
        "excess_net": stats_for("excess_net"),
        "mean_strategy_turnover": float(frame["strategy_turnover"].mean()),
        "mean_eligible_names": float(frame["eligible"].mean()),
        "mean_selected_names": float(frame["selected"].mean()),
    }


def run(panel_path: str, output_prefix: str, cost_bps: float = COST_BPS) -> dict:
    panel = load_panel(panel_path)
    result = evaluate(panel, month_ends(panel), cost_bps=cost_bps)
    result["metadata"] = {
        "panel": panel_path,
        "rows": int(len(panel)),
        "tickers": int(panel["Ticker"].nunique()),
        "date_min": str(panel["Date"].min().date()) if len(panel) else None,
        "date_max": str(panel["Date"].max().date()) if len(panel) else None,
        "horizon_sessions": HORIZON,
        "entry_exit": "next open to open 20 sessions after entry",
        "cost_bps_per_unit_one_way_turnover": cost_bps,
        "weights": WEIGHTS,
        "label": LABEL,
        "known_limitations": [
            "current-universe survivorship bias; not point-in-time constituents",
            "price-only factors; excludes fundamental and event information",
            "monthly overlapping/serially dependent returns limit inference",
            "5 bps cost is a sensitivity assumption, not measured execution cost",
            "no evidence of deployable alpha until independent validation",
        ],
    }
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result["rows"]).to_csv(str(prefix) + ".csv", index=False)
    prefix.with_suffix(".json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-panel", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--cost-bps", type=float, default=COST_BPS)
    args = parser.parse_args(argv)
    result = run(args.price_panel, args.output_prefix, args.cost_bps)
    print(json.dumps({
        "label": LABEL,
        "metadata": result["metadata"],
        "metrics": result["metrics"],
        "observations": len(result["rows"]),
    }, indent=2, ensure_ascii=False))
    return 0 if result["metrics"].get("status") != "INSUFFICIENT_DATA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
