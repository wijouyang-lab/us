#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chronological out-of-sample screen for one predeclared research factor.

Research-only: evaluates Momentum_20D_Pct against stored forward returns. It does not
reproduce the production Scan gate, estimate new weights, place trades, or approve factors.
Uses date-level rank IC and top/bottom cross-sectional spreads with Newey-West HAC t-stats
to account for overlapping forward-return labels within each split.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
INPUT = REPO / "research_backtest_sp500_pit_2y.csv"
OUTPUT = REPO / "docs" / "OOS_MOMENTUM_FACTOR_SCREEN.md"

FACTOR = "Momentum_20D_Pct"
HORIZONS = (5, 10, 20)
TOP_FRACTION = 0.20
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20
PURGE_DATES = max(HORIZONS)
MIN_NAMES_PER_DATE = 30
MIN_TEST_DATES_FOR_SCREEN = 40


def chronological_splits(
    dates: Iterable,
    train_fraction: float = TRAIN_FRACTION,
    validation_fraction: float = VALIDATION_FRACTION,
    purge_dates: int = PURGE_DATES,
) -> dict[str, list[pd.Timestamp]]:
    """Split sorted unique signal dates chronologically, purging labels at boundaries."""
    parsed = sorted({pd.Timestamp(d).normalize() for d in dates if not pd.isna(pd.Timestamp(d))})
    if not (0 < train_fraction < 1 and 0 < validation_fraction < 1
            and train_fraction + validation_fraction < 1):
        raise ValueError("split fractions must be positive and leave a non-empty test interval")
    if purge_dates < 0:
        raise ValueError("purge_dates must be non-negative")
    n = len(parsed)
    train_end = int(n * train_fraction)
    validation_end = int(n * (train_fraction + validation_fraction))
    raw_train = parsed[:train_end]
    raw_validation = parsed[train_end:validation_end]
    test = parsed[validation_end:]
    train = raw_train[:-purge_dates] if purge_dates else raw_train[:]
    validation = raw_validation[:-purge_dates] if purge_dates else raw_validation[:]
    if not train or not validation or not test:
        raise ValueError(
            f"not enough unique dates for chronological split + purge: n={n}, "
            f"train={len(train)}, validation={len(validation)}, test={len(test)}, purge={purge_dates}"
        )
    return {"train": train, "validation": validation, "test": test}


def newey_west_mean_tstat(values: Iterable[float], max_lag: int) -> float | None:
    """HAC t-statistic for a mean, using Bartlett weights; no annualization."""
    x = np.asarray(list(values), dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return None
    mean = float(np.mean(x))
    centered = x - mean
    gamma0 = float(np.dot(centered, centered) / n)
    long_run_var = gamma0
    lag_limit = min(max(0, int(max_lag)), n - 1)
    for lag in range(1, lag_limit + 1):
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / n)
        weight = 1.0 - lag / (lag_limit + 1.0)
        long_run_var += 2.0 * weight * covariance
    if not math.isfinite(long_run_var) or long_run_var <= 0:
        return None
    se_mean = math.sqrt(long_run_var / n)
    if se_mean <= 0 or not math.isfinite(se_mean):
        return None
    return mean / se_mean


def evaluate_factor_segment(
    frame: pd.DataFrame,
    dates: Iterable,
    factor: str = FACTOR,
    horizons: Iterable[int] = HORIZONS,
    top_fraction: float = TOP_FRACTION,
    min_names_per_date: int = MIN_NAMES_PER_DATE,
    direction: int | dict[int, int] = 1,
) -> dict[int, dict]:
    """Evaluate a fixed cross-sectional factor direction for each horizon.

    direction=1 means higher raw factor is stronger; -1 reverses it; 0 skips that
    horizon because the training segment did not define a direction.
    """
    date_set = {pd.Timestamp(d).normalize() for d in dates}
    segment = frame[frame["Scan_Date"].isin(date_set)].copy()
    results = {}
    for horizon in horizons:
        ret_col = f"Forward_Return_{horizon}D"
        dir_h = int(direction.get(int(horizon), 0)) if isinstance(direction, dict) else int(direction)
        spreads, daily_ics, top_returns, bottom_returns, top_win_rates = [], [], [], [], []
        rows_used = 0
        for _, day in segment.groupby("Scan_Date", sort=True):
            valid = day.dropna(subset=[factor, ret_col]).copy()
            if len(valid) < min_names_per_date:
                continue
            valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
            valid[ret_col] = pd.to_numeric(valid[ret_col], errors="coerce")
            valid = valid.replace([np.inf, -np.inf], np.nan).dropna(subset=[factor, ret_col])
            if len(valid) < min_names_per_date or valid[factor].nunique() < 2:
                continue
            if dir_h == 0:
                continue
            k = max(1, int(np.ceil(len(valid) * top_fraction)))
            # Direction is determined from the training segment and must remain fixed
            # for validation/test; it is never refit on held-out outcomes.
            valid["_signal"] = valid[factor] * dir_h
            ordered = valid.sort_values(["_signal", "Ticker"], kind="mergesort")
            bottom = ordered.head(k)
            top = ordered.tail(k)
            top_mean = float(top[ret_col].mean())
            bottom_mean = float(bottom[ret_col].mean())
            spreads.append(top_mean - bottom_mean)
            ic = valid["_signal"].corr(valid[ret_col], method="spearman")
            if pd.notna(ic):
                daily_ics.append(float(ic))
            top_returns.append(top_mean)
            bottom_returns.append(bottom_mean)
            top_win_rates.append(float((top[ret_col] > 0).mean()))
            rows_used += len(valid)

        mean_ic = float(np.mean(daily_ics)) if daily_ics else None
        ic_std = float(np.std(daily_ics, ddof=1)) if len(daily_ics) > 1 else None
        results[int(horizon)] = {
            "direction": dir_h,
            "valid_dates": len(spreads),
            "valid_rows": rows_used,
            "mean_daily_ic": mean_ic,
            "icir_unannualized": (mean_ic / ic_std if mean_ic is not None and ic_std and ic_std > 0 else None),
            "positive_ic_days_pct": (100.0 * sum(v > 0 for v in daily_ics) / len(daily_ics) if daily_ics else None),
            "top_mean_return": float(np.mean(top_returns)) if top_returns else None,
            "bottom_mean_return": float(np.mean(bottom_returns)) if bottom_returns else None,
            "top_bottom_spread": float(np.mean(spreads)) if spreads else None,
            "spread_hac_t": newey_west_mean_tstat(spreads, int(horizon) - 1),
            "top_win_rate_pct": (100.0 * float(np.mean(top_win_rates)) if top_win_rates else None),
        }
    return results


def select_directions_from_train(train_metrics: dict[int, dict], horizons: Iterable[int] = HORIZONS) -> dict[int, int]:
    """Freeze each horizon's signal sign using training-period IC only."""
    directions = {}
    for horizon in horizons:
        ic = train_metrics.get(int(horizon), {}).get("mean_daily_ic")
        directions[int(horizon)] = 1 if ic is not None and ic > 0 else (
            -1 if ic is not None and ic < 0 else 0
        )
    return directions


def classify_test_result(metrics: dict, min_dates: int = MIN_TEST_DATES_FOR_SCREEN) -> str:
    """Conservative per-horizon held-out interpretation; never auto-approves a factor."""
    if int(metrics.get("valid_dates", 0)) < min_dates:
        return f"INSUFFICIENT_TEST_DATES (need >= {min_dates}, got {metrics.get('valid_dates', 0)})"
    spread = metrics.get("top_bottom_spread")
    tstat = metrics.get("spread_hac_t")
    if spread is None or tstat is None:
        return "INSUFFICIENT_OUTCOME_DATA"
    if spread > 0 and tstat >= 1.96:
        return "PRELIMINARY_POSITIVE_ONLY"
    if spread < 0 and tstat <= -1.96:
        return "SIGNIFICANT_NEGATIVE_SPREAD"
    return "NOT_CONFIRMED"


def _pct(v, decimals=3):
    return "N/A" if v is None or not math.isfinite(float(v)) else f"{float(v) * 100:+.{decimals}f}%"


def _fmt(v, decimals=3):
    return "N/A" if v is None or not math.isfinite(float(v)) else f"{float(v):+.{decimals}f}"


def build_report(frame: pd.DataFrame, input_path: Path = INPUT) -> str:
    """Construct a deterministic markdown report from a validated PIT dataset."""
    date_list = sorted(frame["Scan_Date"].dropna().unique())
    splits = chronological_splits(date_list)
    report = [
        "# Chronological OOS screen — 20D Momentum baseline\n",
        "> Status: research-only diagnostic. This is a single, predeclared factor screen, not the production strategy and not an execution backtest.",
        f"> Input: {input_path.name}; {len(frame):,} rows; {frame['Ticker'].nunique():,} tickers; {len(date_list)} signal dates.",
        f"> Period: {pd.Timestamp(date_list[0]).date()} to {pd.Timestamp(date_list[-1]).date()}.",
        f"> Signal: {FACTOR}; direction is selected from TRAIN only per horizon and then frozen for validation/test; daily Top {TOP_FRACTION:.0%} vs Bottom {TOP_FRACTION:.0%}.",
        f"> Split: chronological {TRAIN_FRACTION:.0%}/{VALIDATION_FRACTION:.0%}/{1-TRAIN_FRACTION-VALIDATION_FRACTION:.0%}; purge {PURGE_DATES} signal dates before each next segment so forward-return labels do not straddle split boundaries.",
        "> Test uncertainty: spread t-stat uses Newey-West HAC with lag horizon-1 to account for overlapping forward-return labels; this is not a full trading-cost-adjusted return estimate.\n",
        "## Chronological date partitions\n",
        "| Segment | First signal date | Last signal date | Used signal dates |",
        "|---|---|---|---:|",
    ]
    for name in ("train", "validation", "test"):
        ds = splits[name]
        report.append(f"| {name.title()} | {ds[0].date()} | {ds[-1].date()} | {len(ds)} |")

    report += [
        "",
        "## Fixed-factor results by split\n",
        "| Segment | Horizon | Valid dates | Rows | Mean daily rank IC | Positive IC days | Top 20% mean return | Bottom 20% mean return | Top-bottom spread | HAC t-stat | Top win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    # Select each horizon's sign from TRAIN outcomes only; then freeze for all later data.
    train_raw = evaluate_factor_segment(frame, splits["train"], direction=1)
    directions = select_directions_from_train(train_raw)
    metrics = {}
    for name in ("train", "validation", "test"):
        metrics[name] = evaluate_factor_segment(frame, splits[name], direction=directions)
        for horizon in HORIZONS:
            m = metrics[name][horizon]
            positive_ic = "N/A" if m["positive_ic_days_pct"] is None else f"{m['positive_ic_days_pct']:.1f}%"
            top_win = "N/A" if m["top_win_rate_pct"] is None else f"{m['top_win_rate_pct']:.1f}%"
            report.append(
                f"| {name.title()} | {horizon}D | {m['valid_dates']} | {m['valid_rows']:,} | "
                f"{_fmt(m['mean_daily_ic'], 4)} | {positive_ic} | "
                f"{_pct(m['top_mean_return'])} | {_pct(m['bottom_mean_return'])} | "
                f"{_pct(m['top_bottom_spread'])} | {_fmt(m['spread_hac_t'], 2)} | {top_win} |"
            )

    test_verdicts = {
        horizon: classify_test_result(metrics["test"][horizon])
        for horizon in HORIZONS
    }
    verdict = test_verdicts[20]
    report += [
        "",
        "## TRAIN-only direction lock\n",
        *[
            f"- {horizon}D selected direction: "
            + ("higher factor value" if directions[horizon] == 1
               else "lower factor value" if directions[horizon] == -1
               else "undetermined; this horizon is not evaluated")
            for horizon in HORIZONS
        ],
        "",
        "## Held-out test verdicts by horizon\n",
        "| Horizon | Test verdict | Top-bottom spread | HAC t-stat | Valid dates |",
        "|---|---|---:|---:|---:|",
        *[
            f"| {horizon}D | {test_verdicts[horizon]} | "
            f"{_pct(metrics['test'][horizon]['top_bottom_spread'])} | "
            f"{_fmt(metrics['test'][horizon]['spread_hac_t'], 2)} | "
            f"{metrics['test'][horizon]['valid_dates']} |"
            for horizon in HORIZONS
        ],
        "",
        "## Test-set interpretation\n",
        f"- 20D spread verdict: **{verdict}**.",
        "- A positive result is only preliminary factor evidence. It does not validate the production Core/Observation gate, stop-loss execution, fills, fees, slippage, or live profitability.",
        "- A non-positive / statistically weak result does not prove every use of the factor is worthless; it means this fixed high-vs-low screen was not confirmed in the held-out period.",
        "- PIT membership uses the repository's historical constituent/date rules; it cannot guarantee freedom from all survivorship, delisting, data-vendor, or corporate-action issues.",
        "- Do not adjust the factor direction, Top fraction, split boundary, or other settings after seeing the test result and still call this same segment an untouched test set.",
        "",
    ]
    return "\n".join(report)


def main() -> int:
    if not INPUT.exists() or INPUT.stat().st_size == 0:
        raise SystemExit(f"missing or empty research input: {INPUT}")
    frame = pd.read_csv(INPUT, dtype=str, keep_default_na=False)
    required = {"Scan_Date", "Ticker", FACTOR, *(f"Forward_Return_{h}D" for h in HORIZONS)}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SystemExit(f"missing required columns: {missing}")
    frame["Scan_Date"] = pd.to_datetime(frame["Scan_Date"], errors="coerce").dt.normalize()
    frame[FACTOR] = pd.to_numeric(frame[FACTOR].replace("", np.nan), errors="coerce")
    for horizon in HORIZONS:
        col = f"Forward_Return_{horizon}D"
        frame[col] = pd.to_numeric(frame[col].replace("", np.nan), errors="coerce")
    if frame["Scan_Date"].isna().any():
        raise SystemExit(f"invalid Scan_Date rows: {int(frame['Scan_Date'].isna().sum())}")
    if frame.duplicated(["Scan_Date", "Ticker"]).any():
        raise SystemExit("duplicate Scan_Date|Ticker rows; refusing silent de-duplication")
    if "Technical_Date" in frame.columns:
        frame["Technical_Date"] = pd.to_datetime(frame["Technical_Date"], errors="coerce").dt.normalize()
        future_technical = frame["Technical_Date"] > frame["Scan_Date"]
        if future_technical.any():
            raise SystemExit(f"Technical_Date later than Scan_Date in {int(future_technical.sum())} rows")
    frame["Ticker"] = frame["Ticker"].astype(str).str.strip().str.upper()
    frame = frame.dropna(subset=[FACTOR])
    report = build_report(frame)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
