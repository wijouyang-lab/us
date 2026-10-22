#!/usr/bin/env python3
"""Build a research-only complete-history cohort and adjusted-close drawdown report.

This does not alter the PIT refresh audit or production data. Coverage is measured
only on SPY trading sessions during each ticker's documented index membership.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

try:  # Support both package imports in tests and direct script execution.
    from .multi_index_membership import load_multi_index_membership
except ImportError:  # pragma: no cover - exercised by CLI invocation
    from multi_index_membership import load_multi_index_membership

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PRICES = REPO / "research_price_history_sp500_10y.csv"
DEFAULT_SPY = REPO / "research_spy_sp500_10y.csv"
DEFAULT_MEMBERSHIP = REPO / "tools/research/data/sp500_components_history.csv"
DEFAULT_ALIASES = REPO / "tools/research/data/sp500_ticker_aliases.csv"
DEFAULT_NASDAQ100 = REPO / "tools/research/data/nasdaq100_membership_history.csv"
DEFAULT_DOW30 = REPO / "tools/research/data/dow30_membership_history.csv"
DEFAULT_OUT = REPO / "research_complete_history"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required research input does not exist: {path}")
    return pd.read_csv(path)


def _date_column(frame: pd.DataFrame, label: str) -> pd.Series:
    if "Date" not in frame.columns:
        raise ValueError(f"{label} must contain a Date column")
    return pd.to_datetime(frame["Date"], errors="coerce").dt.date


def build_reports(
    prices: pd.DataFrame,
    spy: pd.DataFrame,
    membership: dict,
    *,
    min_coverage: float = 0.90,
    min_valid_rows: int = 252,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return ticker coverage, drawdown episodes, and summary without writing files."""
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage must be in (0, 1]")
    required = {"Date", "Ticker", "Adj Close"}
    if not required.issubset(prices.columns):
        raise ValueError(f"prices must contain columns: {', '.join(sorted(required))}")

    p = prices.copy()
    p["Date"] = _date_column(p, "prices")
    p["Ticker"] = p["Ticker"].astype(str).str.strip().str.upper()
    p["Adj Close"] = pd.to_numeric(p["Adj Close"], errors="coerce")
    p = p.dropna(subset=["Date", "Ticker", "Adj Close"])
    p = p[(p["Adj Close"] > 0) & (p["Ticker"] != "")]
    p = p.drop_duplicates(["Ticker", "Date"], keep="last").sort_values(["Ticker", "Date"])

    s = spy.copy()
    s["Date"] = _date_column(s, "SPY")
    sessions = sorted(set(s["Date"].dropna()))
    if not sessions:
        raise ValueError("SPY input contains no valid trading-session dates")
    coverage_rows = []
    drawdown_rows = []
    for ticker, intervals in sorted(membership.items()):
        ticker_prices = p[p["Ticker"] == ticker].set_index("Date")["Adj Close"].sort_index()
        expected = set()
        for interval in intervals:
            expected.update(
                day for day in sessions
                if interval.date_added <= day
                and (interval.date_removed is None or day < interval.date_removed)
            )
        observed = expected.intersection(set(ticker_prices.index))
        coverage = len(observed) / len(expected) if expected else 0.0
        valid = len(observed)
        eligible = coverage >= min_coverage and valid >= min_valid_rows
        coverage_rows.append({
            "Ticker": ticker,
            "Expected_Member_Sessions": len(expected),
            "Observed_Valid_Sessions": valid,
            "Session_Coverage": round(coverage, 6),
            "Min_Coverage_Required": min_coverage,
            "Min_Valid_Rows_Required": min_valid_rows,
            "Eligible_For_Drawdown_Research": eligible,
            "Exclusion_Reason": "" if eligible else (
                "no_membership_sessions" if not expected else
                "coverage_below_threshold" if coverage < min_coverage else
                "insufficient_valid_rows"
            ),
        })
        if not eligible:
            continue

        # Calculate drawdown from split/dividend-adjusted closes; do not mix raw Close.
        series = ticker_prices.loc[sorted(observed)].astype(float)
        peaks = series.cummax()
        dd = series / peaks - 1.0
        if dd.empty:
            continue
        trough_date = dd.idxmin()
        trough_value = float(dd.loc[trough_date])
        peak_date = series.loc[:trough_date].idxmax()
        peak_value = float(series.loc[peak_date])
        recovery = series.loc[trough_date:]
        recovered = recovery[recovery >= peak_value]
        recovery_date = recovered.index[0] if not recovered.empty else None
        drawdown_rows.append({
            "Ticker": ticker,
            "Coverage": round(coverage, 6),
            "Observed_Sessions": valid,
            "Peak_Date": peak_date.isoformat(),
            "Peak_Adj_Close": round(peak_value, 6),
            "Trough_Date": trough_date.isoformat(),
            "Trough_Adj_Close": round(float(series.loc[trough_date]), 6),
            "Max_Drawdown_Pct": round(trough_value * 100, 4),
            "Recovery_Date": recovery_date.isoformat() if recovery_date else "",
            "Recovered": bool(recovery_date),
        })

    coverage_df = pd.DataFrame(coverage_rows)
    if not coverage_df.empty:
        coverage_df = coverage_df.sort_values(
            ["Eligible_For_Drawdown_Research", "Session_Coverage", "Ticker"],
            ascending=[False, False, True],
        )
    drawdown_df = pd.DataFrame(drawdown_rows)
    if not drawdown_df.empty:
        drawdown_df = drawdown_df.sort_values("Max_Drawdown_Pct")
    eligible_count = int(coverage_df["Eligible_For_Drawdown_Research"].sum()) if not coverage_df.empty else 0
    summary = {
        "status": "exploratory_research_only",
        "min_coverage": min_coverage,
        "min_valid_rows": min_valid_rows,
        "membership_tickers_evaluated": int(len(coverage_df)),
        "eligible_tickers": eligible_count,
        "excluded_tickers": int(len(coverage_df) - eligible_count),
        "drawdown_tickers_reported": int(len(drawdown_df)),
        "price_date_min": min(p["Date"]).isoformat() if not p.empty else None,
        "price_date_max": max(p["Date"]).isoformat() if not p.empty else None,
        "session_date_min": sessions[0].isoformat(),
        "session_date_max": sessions[-1].isoformat(),
        "warning": "A passing cohort is not proof of unbiased historical performance; delisted-stock coverage and data freshness must still be reviewed.",
    }
    return coverage_df, drawdown_df, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--spy", type=Path, default=DEFAULT_SPY)
    parser.add_argument("--membership", type=Path, default=DEFAULT_MEMBERSHIP)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    parser.add_argument("--nasdaq100-membership", type=Path, default=DEFAULT_NASDAQ100)
    parser.add_argument("--dow30-membership", type=Path, default=DEFAULT_DOW30)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--min-coverage", type=float, default=1.0)
    parser.add_argument("--min-valid-rows", type=int, default=252)
    args = parser.parse_args()

    membership = load_multi_index_membership(
        args.membership, args.aliases, args.nasdaq100_membership, args.dow30_membership
    )
    coverage, drawdowns, summary = build_reports(
        _read_csv(args.prices), _read_csv(args.spy), membership,
        min_coverage=args.min_coverage, min_valid_rows=args.min_valid_rows,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(args.out_dir / "ticker_coverage.csv", index=False)
    coverage.loc[coverage["Eligible_For_Drawdown_Research"]].to_csv(
        args.out_dir / "eligible_tickers.csv", index=False
    )
    coverage.loc[~coverage["Eligible_For_Drawdown_Research"]].to_csv(
        args.out_dir / "excluded_tickers.csv", index=False
    )
    drawdowns.to_csv(args.out_dir / "max_drawdowns.csv", index=False)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
