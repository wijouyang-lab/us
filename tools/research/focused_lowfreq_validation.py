#!/usr/bin/env python3
"""Fixed, research-only low-frequency factor check.

This is deliberately not a factor search.  It evaluates five economically
motivated directions on an existing PIT snapshot and reports the result even
when nothing survives multiple-testing correction.

No production scanner, ledger, or trading module is imported.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# Fixed before this script's historical evaluation.  Do not add/adjust a
# direction after looking at the output.
FACTORS = {
    "ATR_Pct": ("ATR_Pct", -1, "low volatility"),
    "Realized_Volatility_20D_Pct": ("Realized_Volatility_20D_Pct", -1, "low realized volatility"),
    "Momentum_60D_Pct": ("Momentum_60D_Pct", 1, "60-session momentum"),
    "RSI": ("RSI", -1, "short-term reversal (low RSI)"),
    "Volume_Ratio_20D": ("Volume_Ratio_20D", 1, "relative volume"),
}
HORIZON = 20
REBALANCE_SESSIONS = 20
WINSOR_LIMIT = 0.01
ONE_WAY_COST_BPS = 5.0
MIN_NAMES = 50


def prepare_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    required = {"Technical_Date", "Ticker", "Price", *[v[0] for v in FACTORS.values()]}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Technical_Date"], errors="coerce")
    out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
    out["Price"] = pd.to_numeric(out["Price"], errors="coerce")
    out = out.dropna(subset=["Date", "Ticker", "Price"])
    out = out[out["Ticker"] != ""].sort_values(["Ticker", "Date"])
    if out.empty:
        raise SystemExit("Snapshot contains no usable rows")
    return out


def load_snapshot(path: str | Path) -> pd.DataFrame:
    return prepare_snapshot(pd.read_csv(path, low_memory=False))


def add_forward_return(df: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    out = df.copy()
    out["Forward_Return"] = (
        out.groupby("Ticker", sort=False)["Price"].shift(-horizon) / out["Price"] - 1.0
    )
    return out


def rebalance_dates(df: pd.DataFrame, interval: int = REBALANCE_SESSIONS) -> list[pd.Timestamp]:
    sessions = sorted(pd.to_datetime(df["Date"]).dropna().unique())
    return list(sessions[::interval])


def bh_qvalues(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values for the fixed family of five tests."""
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    raw = ranked * n / np.arange(1, n + 1)
    q_sorted = np.minimum.accumulate(raw[::-1])[::-1]
    q_sorted = np.minimum(q_sorted, 1.0)
    q = np.empty(n, dtype=float)
    q[order] = q_sorted
    return q.tolist()


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rebalances = rebalance_dates(df)
    for name, (column, direction, rationale) in FACTORS.items():
        spreads = []
        usable_dates = 0
        for day in rebalances:
            x = df.loc[df["Date"] == day, ["Ticker", column, "Forward_Return"]].copy()
            x[column] = pd.to_numeric(x[column], errors="coerce")
            x = x.dropna(subset=[column, "Forward_Return"])
            if len(x) < MIN_NAMES:
                continue
            usable_dates += 1
            lo, hi = x["Forward_Return"].quantile([WINSOR_LIMIT, 1 - WINSOR_LIMIT])
            x["_ret"] = x["Forward_Return"].clip(lo, hi)
            rank = x[column].rank(pct=True, method="average")
            q5 = x.loc[rank >= 0.8, "_ret"].mean()
            q1 = x.loc[rank <= 0.2, "_ret"].mean()
            if pd.notna(q5) and pd.notna(q1):
                spreads.append(float(direction * (q5 - q1)))
        if len(spreads) < 3:
            rows.append({
                "factor": name, "direction": direction, "rationale": rationale,
                "n_rebalances": len(spreads), "gross_mean": None, "net_5bps": None,
                "positive_pct": None, "t_stat": None, "p_value": None, "q_value_bh": None,
            })
            continue
        s = pd.Series(spreads, dtype=float)
        mean = float(s.mean())
        sd = float(s.std(ddof=1))
        t_stat = mean / (sd / np.sqrt(len(s))) if sd > 0 else float("nan")
        p_value = float(2 * stats.t.sf(abs(t_stat), len(s) - 1)) if np.isfinite(t_stat) else 1.0
        round_trip_cost = 2 * ONE_WAY_COST_BPS / 10000.0
        rows.append({
            "factor": name, "direction": direction, "rationale": rationale,
            "n_rebalances": len(spreads),
            "gross_mean": mean,
            "net_5bps": mean - round_trip_cost,
            "positive_pct": float((s > 0).mean()),
            "t_stat": t_stat,
            "p_value": p_value,
            "q_value_bh": None,
            "usable_dates": usable_dates,
        })
    out = pd.DataFrame(rows)
    valid = out["p_value"].notna()
    if valid.any():
        out.loc[valid, "q_value_bh"] = bh_qvalues(out.loc[valid, "p_value"].tolist())
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="research_factor_snapshots_sp500_pit_2y.csv")
    parser.add_argument("--output", default="research_focused_lowfreq_validation.json")
    args = parser.parse_args(argv)

    raw = load_snapshot(args.snapshot)
    labeled = add_forward_return(raw)
    report = evaluate(labeled)
    payload = {
        "research_only": True,
        "snapshot": args.snapshot,
        "rows": int(len(raw)),
        "dates": int(raw["Date"].nunique()),
        "tickers": int(raw["Ticker"].nunique()),
        "date_min": str(raw["Date"].min().date()),
        "date_max": str(raw["Date"].max().date()),
        "horizon_sessions": HORIZON,
        "rebalance_sessions": REBALANCE_SESSIONS,
        "winsor_limit": WINSOR_LIMIT,
        "one_way_cost_bps": ONE_WAY_COST_BPS,
        "cost_assumption": "full long/short turnover each rebalance (2 legs)",
        "results": report.to_dict(orient="records"),
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report.to_string(index=False))
    print(f"n rebalances: {len(rebalance_dates(raw))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
