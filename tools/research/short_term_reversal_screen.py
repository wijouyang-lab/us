#!/usr/bin/env python3
"""Research-only short-term relative-reversal event screen.

This is an event study, not a portfolio NAV backtest. Signals are formed after
the close, entries use the next SPY session Open, and exits use the Open after
exactly H additional SPY sessions. Missing prices are never forward-filled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

LABEL = "EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED"
HORIZONS = (1, 3, 5)
REGIMES = ("RISK_ON", "RISK_OFF", "TRANSITION")
TOP_FRACTION = 0.20
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME_20D = 5_000_000.0
MIN_NAMES = 80
COSTS_BPS = (5, 10, 20, 50)


def _clean_prices(frame: pd.DataFrame, *, name: str, require_ticker: bool) -> pd.DataFrame:
    required = {"Date", "Open", "Close"}
    if require_ticker:
        required |= {"Ticker", "Volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")
    d = frame.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce").dt.normalize()
    if require_ticker:
        d["Ticker"] = d["Ticker"].astype(str).str.strip().str.upper()
        if (d["Ticker"] == "").any():
            raise ValueError(f"{name}: blank ticker")
    for col in ("Open", "Close", "Volume"):
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date"])
    keys = ["Date", "Ticker"] if require_ticker else ["Date"]
    if d.duplicated(keys).any():
        sample = d.loc[d.duplicated(keys, keep=False), keys].head(5).to_dict("records")
        raise ValueError(f"{name}: duplicate session keys: {sample}")
    for col in ("Open", "Close"):
        if col in d:
            d.loc[d[col] <= 0, col] = np.nan
    return d.sort_values(keys).reset_index(drop=True)


def classify_market_regime(spy: pd.DataFrame) -> pd.DataFrame:
    """Classify from same-day close only; no forward data are used."""
    s = _clean_prices(spy, name="SPY", require_ticker=False)
    s = s.sort_values("Date").reset_index(drop=True)
    s["MA200"] = s["Close"].rolling(200, min_periods=200).mean()
    s["MA200_Slope20"] = s["MA200"] / s["MA200"].shift(20) - 1.0
    risk_on = (s["Close"] > s["MA200"]) & (s["MA200_Slope20"] > 0)
    risk_off = (s["Close"] < s["MA200"]) & (s["MA200_Slope20"] < 0)
    s["Regime"] = np.select(
        [risk_on.fillna(False), risk_off.fillna(False)],
        ["RISK_ON", "RISK_OFF"],
        default="TRANSITION",
    )
    s["SPY_Ret5"] = s["Close"].pct_change(5, fill_method=None)
    return s.set_index("Date", drop=False)


def hac_mean_test(values: Iterable[float], max_lag: int) -> dict:
    """Newey-West HAC inference for a mean, using Bartlett weights."""
    x = np.asarray(list(values), dtype=float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n < max(10, max_lag + 2):
        return {"n": n, "mean": float(np.mean(x)) if n else None,
                "se_hac": None, "t_hac": None, "p_two_sided_normal": None,
                "ci95_low": None, "ci95_high": None}
    mu = float(np.mean(x))
    z = x - mu
    gamma0 = float(np.dot(z, z) / n)
    long_run_var = gamma0
    lag_limit = min(max(0, int(max_lag)), n - 1)
    for lag in range(1, lag_limit + 1):
        gamma = float(np.dot(z[lag:], z[:-lag]) / n)
        weight = 1.0 - lag / (lag_limit + 1.0)
        long_run_var += 2.0 * weight * gamma
    if not math.isfinite(long_run_var) or long_run_var <= 0:
        return {"n": n, "mean": mu, "se_hac": None, "t_hac": None,
                "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None}
    se = math.sqrt(long_run_var / n)
    t_stat = mu / se if se > 0 else None
    p_value = math.erfc(abs(t_stat) / math.sqrt(2.0)) if t_stat is not None else None
    return {"n": n, "mean": mu, "se_hac": se, "t_hac": t_stat,
            "p_two_sided_normal": p_value,
            "ci95_low": mu - 1.96 * se, "ci95_high": mu + 1.96 * se}


def benjamini_hochberg(p_values: dict[str, float | None]) -> dict[str, float | None]:
    valid = [(key, float(value)) for key, value in p_values.items()
             if value is not None and math.isfinite(float(value))]
    valid.sort(key=lambda item: item[1])
    m = len(valid)
    adjusted: dict[str, float | None] = {key: None for key in p_values}
    running = 1.0
    for rank in range(m, 0, -1):
        key, p_value = valid[rank - 1]
        running = min(running, p_value * m / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


def _prepare_panels(stocks: pd.DataFrame, spy: pd.DataFrame):
    stock = _clean_prices(stocks, name="stocks", require_ticker=True)
    market = classify_market_regime(spy)
    calendar = pd.DatetimeIndex(market.index).sort_values()
    if len(calendar) < 250:
        raise ValueError(f"SPY calendar too short for 200D regime: {len(calendar)} sessions")
    stock = stock[stock["Date"].isin(calendar)].copy()
    if stock.empty:
        raise ValueError("stock panel has no dates in common with SPY")
    tickers = sorted(stock["Ticker"].unique())
    close = stock.pivot(index="Date", columns="Ticker", values="Close").reindex(calendar)
    open_ = stock.pivot(index="Date", columns="Ticker", values="Open").reindex(calendar)
    volume = stock.pivot(index="Date", columns="Ticker", values="Volume").reindex(calendar)
    dollar_volume = (close * volume).rolling(20, min_periods=20).mean()
    ret5 = close.pct_change(5, fill_method=None)
    relative_ret5 = ret5.sub(market["SPY_Ret5"], axis=0)
    return {
        "calendar": calendar, "tickers": tickers, "close": close, "open": open_,
        "dollar_volume_20d": dollar_volume, "relative_ret5": relative_ret5,
        "market": market, "stock_rows": len(stock),
    }


def build_event_rows(
    stocks: pd.DataFrame,
    spy: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    min_names: int = MIN_NAMES,
    top_fraction: float = TOP_FRACTION,
    min_price: float = MIN_PRICE,
    min_dollar_volume_20d: float = MIN_DOLLAR_VOLUME_20D,
    start: str = "2018-01-01",
) -> tuple[pd.DataFrame, dict]:
    """Build daily event observations from information available at signal close.

    The selected basket is fixed before looking at future prices. If any selected
    name lacks an exact entry or exit Open, that event is rejected. The equal-
    weight universe benchmark uses only eligible names with exact prices and
    reports its coverage count.
    """
    p = _prepare_panels(stocks, spy)
    calendar = p["calendar"]
    close, open_ = p["close"], p["open"]
    dv20, rel5, market = p["dollar_volume_20d"], p["relative_ret5"], p["market"]
    start_ts = pd.Timestamp(start).normalize()
    rows: list[dict] = []
    counts = {
        "signal_dates_seen": 0, "insufficient_universe": 0,
        "missing_selected_execution_events": 0, "missing_universe_execution_names": 0,
        "missing_spy_execution_events": 0, "usable_events_by_horizon": {},
    }
    max_h = max(horizons)
    for i, signal_date in enumerate(calendar):
        if signal_date < start_ts or i < 200 or i + 1 + max_h >= len(calendar):
            continue
        counts["signal_dates_seen"] += 1
        regime = str(market.loc[signal_date, "Regime"])
        signal_close = close.loc[signal_date]
        signal_dv = dv20.loc[signal_date]
        signal_rel = rel5.loc[signal_date]
        eligible_mask = (
            (signal_close >= min_price)
            & (signal_dv >= min_dollar_volume_20d)
            & signal_rel.notna()
        )
        eligible = sorted(signal_close.index[eligible_mask].tolist())
        if len(eligible) < min_names:
            counts["insufficient_universe"] += 1
            continue
        pick_count = max(1, int(len(eligible) * top_fraction))
        selected = signal_rel.loc[eligible].sort_values(kind="mergesort").head(pick_count).index.tolist()
        if not selected:
            continue

        for horizon in horizons:
            entry_date, exit_date = calendar[i + 1], calendar[i + 1 + horizon]
            spy_entry, spy_exit = market.loc[entry_date, "Open"], market.loc[exit_date, "Open"]
            if pd.isna(spy_entry) or pd.isna(spy_exit) or spy_entry <= 0 or spy_exit <= 0:
                counts["missing_spy_execution_events"] += 1
                continue
            entry, exit_ = open_.loc[entry_date, eligible], open_.loc[exit_date, eligible]
            valid = entry.notna() & exit_.notna() & (entry > 0) & (exit_ > 0)
            valid_names = valid[valid].index.tolist()
            counts["missing_universe_execution_names"] += len(eligible) - len(valid_names)
            if any(ticker not in valid_names for ticker in selected):
                counts["missing_selected_execution_events"] += 1
                continue
            if len(valid_names) < min_names:
                counts["insufficient_universe"] += 1
                continue
            selected_ret = (exit_.loc[selected] / entry.loc[selected] - 1.0).astype(float)
            universe_ret = (exit_.loc[valid_names] / entry.loc[valid_names] - 1.0).astype(float)
            rows.append({
                "signal_date": signal_date, "signal_session_index": int(i),
                "entry_date": entry_date, "exit_date": exit_date,
                "horizon": int(horizon), "regime": regime,
                "eligible_names": int(len(eligible)), "selected_names": int(len(selected)),
                "benchmark_names": int(len(valid_names)),
                "gross_return": float(selected_ret.mean()),
                "equal_weight_return": float(universe_ret.mean()),
                "spy_return": float(spy_exit / spy_entry - 1.0),
            })
    events = pd.DataFrame(rows)
    if not events.empty:
        events = events.sort_values(["horizon", "signal_date"]).reset_index(drop=True)
    for horizon in horizons:
        counts["usable_events_by_horizon"][str(horizon)] = (
            int((events["horizon"] == horizon).sum()) if not events.empty else 0
        )
    counts["stock_rows_common_calendar"] = int(p["stock_rows"])
    counts["tickers"] = int(len(p["tickers"]))
    counts["calendar_sessions"] = int(len(calendar))
    counts["calendar_start"] = calendar.min().date().isoformat()
    counts["calendar_end"] = calendar.max().date().isoformat()
    return events, counts


def _period_filter(events: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    return events[(events.signal_date >= lo) & (events.signal_date <= hi) & (events.exit_date <= hi)]


def summarize_cell(events: pd.DataFrame, cost_bps: int) -> dict:
    if events.empty:
        empty_hac = {"n": 0, "mean": None, "se_hac": None, "t_hac": None,
                     "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None,
                     "mean_pct": None, "se_pct": None, "ci95_low_pct": None, "ci95_high_pct": None}
        return {
            "n_events": 0, "status": "INSUFFICIENT_DATA",
            "mean_gross_return_pct": None, "median_gross_return_pct": None,
            "mean_net_return_pct": None, "median_net_return_pct": None,
            "mean_equal_weight_return_pct": None, "mean_spy_return_pct": None,
            "mean_net_excess_vs_equal_weight_pct": None,
            "median_net_excess_vs_equal_weight_pct": None,
            "mean_net_excess_vs_spy_pct": None,
            "median_net_excess_vs_spy_pct": None, "win_rate_pct": None,
            "n_non_overlapping_events": 0,
            "round_trip_cost_bps": int(2 * cost_bps),
            "hac_net_excess_vs_equal_weight": empty_hac,
            "hac_net_excess_vs_spy": empty_hac,
        }
    round_trip_cost = 2.0 * float(cost_bps) / 10_000.0
    gross = events["gross_return"].to_numpy(float)
    net = gross - round_trip_cost
    ew = events["equal_weight_return"].to_numpy(float)
    spy = events["spy_return"].to_numpy(float)
    excess_ew, excess_spy = net - ew, net - spy
    horizon = int(events["horizon"].iloc[0])
    ew_test = hac_mean_test(excess_ew, max_lag=max(0, horizon - 1))
    spy_test = hac_mean_test(excess_spy, max_lag=max(0, horizon - 1))
    def percent_test(test):
        return {
            **test,
            "mean_pct": None if test["mean"] is None else test["mean"] * 100,
            "se_pct": None if test["se_hac"] is None else test["se_hac"] * 100,
            "ci95_low_pct": None if test["ci95_low"] is None else test["ci95_low"] * 100,
            "ci95_high_pct": None if test["ci95_high"] is None else test["ci95_high"] * 100,
        }
    # Greedy, chronological, non-overlapping event count. Event windows are
    # [entry Open, exit Open]; a new event may start on the prior exit Open.
    ordered = events.sort_values("signal_session_index")
    next_allowed = -10**12
    non_overlap_count = 0
    for session_index in ordered["signal_session_index"].astype(int):
        if session_index >= next_allowed:
            non_overlap_count += 1
            next_allowed = session_index + horizon
    return {
        "n_events": int(len(events)),
        "n_non_overlapping_events": int(non_overlap_count),
        "mean_gross_return_pct": float(np.mean(gross) * 100),
        "median_gross_return_pct": float(np.median(gross) * 100),
        "mean_net_return_pct": float(np.mean(net) * 100),
        "median_net_return_pct": float(np.median(net) * 100),
        "mean_equal_weight_return_pct": float(np.mean(ew) * 100),
        "mean_spy_return_pct": float(np.mean(spy) * 100),
        "mean_net_excess_vs_equal_weight_pct": float(np.mean(excess_ew) * 100),
        "median_net_excess_vs_equal_weight_pct": float(np.median(excess_ew) * 100),
        "mean_net_excess_vs_spy_pct": float(np.mean(excess_spy) * 100),
        "median_net_excess_vs_spy_pct": float(np.median(excess_spy) * 100),
        "win_rate_pct": float(np.mean(net > 0) * 100),
        "hac_net_excess_vs_equal_weight": percent_test(ew_test),
        "hac_net_excess_vs_spy": percent_test(spy_test),
        "round_trip_cost_bps": int(2 * cost_bps),
        "interpretation": "overlapping event returns; not a portfolio CAGR or Sharpe",
    }


def run_screen(stocks: pd.DataFrame, spy: pd.DataFrame, *, start: str = "2018-01-01") -> dict:
    events, input_audit = build_event_rows(stocks, spy, start=start)
    if events.empty:
        raise ValueError("no usable event rows; inspect data coverage and minimum-universe filters")
    max_date = input_audit["calendar_end"]
    periods = {
        "development_2018_2020": ("2018-01-01", "2020-12-31"),
        "validation_2021_2023": ("2021-01-01", "2023-12-31"),
        "later_period_2024_plus": ("2024-01-01", max_date),
    }
    summary: dict[str, dict] = {}
    for period_name, (lo, hi) in periods.items():
        period_events = _period_filter(events, lo, hi)
        summary[period_name] = {}
        for horizon in HORIZONS:
            summary[period_name][str(horizon)] = {}
            for regime in REGIMES:
                cell = period_events[
                    (period_events.horizon == horizon) & (period_events.regime == regime)
                ]
                summary[period_name][str(horizon)][regime] = {
                    "costs": {str(cost): summarize_cell(cell, cost) for cost in COSTS_BPS}
                }

    p_values = {}
    for horizon in HORIZONS:
        for regime in REGIMES:
            key = f"H{horizon}:{regime}"
            cell = summary["later_period_2024_plus"][str(horizon)][regime]["costs"]["10"]
            p_values[key] = cell["hac_net_excess_vs_equal_weight"]["p_two_sided_normal"]
    adjusted = benjamini_hochberg(p_values)
    for horizon in HORIZONS:
        for regime in REGIMES:
            key = f"H{horizon}:{regime}"
            cell = summary["later_period_2024_plus"][str(horizon)][regime]["costs"]["10"]
            cell["hac_net_excess_vs_equal_weight"]["p_bh_q_value_family_9"] = adjusted[key]

    return {
        "label": LABEL,
        "status": "EXPLORATORY_EVENT_STUDY_NOT_STRATEGY_VALIDATION",
        "input_audit": input_audit,
        "signal": "bottom 20% of 5-session stock return relative to SPY",
        "execution": "signal after close; next SPY session Open entry; exit after exact H SPY sessions",
        "horizons_sessions": list(HORIZONS),
        "primary_horizon_sessions": 3,
        "market_regime": {
            "RISK_ON": "SPY Close > MA200 and MA200 20-session slope > 0",
            "RISK_OFF": "SPY Close < MA200 and MA200 20-session slope < 0",
            "TRANSITION": "all other observations",
        },
        "universe_limits": [
            "stock history was downloaded for the current S&P 500 Wikipedia list",
            "historical membership filters cannot restore removed/delisted stocks absent from the price input",
            "survivorship bias remains; no claim of complete point-in-time membership",
        ],
        "return_limits": [
            "split-adjusted price returns only; dividends are not credited",
            "event returns overlap across daily signal dates",
            "HAC standard errors use lag H-1; normal-approximation p-values are descriptive",
            "round-trip costs are a simple full-notional event stress, not turnover/fill-level simulation",
            "the 2024+ period is reused research data, not an untouched holdout",
        ],
        "periods": periods,
        "event_signal_date_range": {
            "start": events.signal_date.min().date().isoformat(),
            "end": events.signal_date.max().date().isoformat(),
        },
        "event_counts": {
            period: {
                str(h): {
                    regime: summary[period][str(h)][regime]["costs"]["10"]["n_events"]
                    for regime in REGIMES
                } for h in HORIZONS
            } for period in periods
        },
        "summary": summary,
        "multiple_testing": {
            "method": "Benjamini-Hochberg",
            "family": "later_period 2024+; 3 horizons x 3 regimes; 10 bps per side",
            "raw_p_values": p_values,
            "q_values": adjusted,
            "not_confirmatory": True,
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_report(result: dict) -> str:
    lines = [
        "# Short-Term Relative-Reversal Screen (Research Only)", "",
        f"> Status: {result['status']}. This is an event study, not a portfolio backtest or deployable strategy.",
        f"> Data label: {result['label']}. Survivorship bias and price-return limitations remain.", "",
        f"- Signal: {result['signal']}.",
        f"- Execution: {result['execution']}.",
        f"- Primary horizon: {result['primary_horizon_sessions']} sessions; robustness horizons: 1 and 5.",
        f"- Signal dates: {result['event_signal_date_range']['start']} to {result['event_signal_date_range']['end']}.",
        f"- Input sessions: {result['input_audit']['calendar_sessions']:,}; tickers: {result['input_audit']['tickers']:,}.",
        "",
        "## Later-period regime results (2024+, 10 bps per side)", "",
        "| Horizon | Regime | Events | Non-overlap | Net mean % | Median excess vs EW % | Mean excess vs EW % | HAC t | HAC 95% CI | BH q |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    later = result["summary"]["later_period_2024_plus"]
    def fmt(value, digits=3):
        return "NA" if value is None else f"{value:+.{digits}f}"
    for horizon in HORIZONS:
        for regime in REGIMES:
            cell = later[str(horizon)][regime]["costs"]["10"]
            hac = cell["hac_net_excess_vs_equal_weight"]
            lines.append(
                f"| {horizon} | {regime} | {cell['n_events']} | {cell['n_non_overlapping_events']} | "
                f"{fmt(cell.get('mean_net_return_pct'))} | "
                f"{fmt(cell.get('median_net_excess_vs_equal_weight_pct'))} | "
                f"{fmt(cell.get('mean_net_excess_vs_equal_weight_pct'))} | "
                f"{fmt(hac.get('t_hac'), 2)} | "
                f"[{fmt(hac.get('ci95_low_pct'))}, {fmt(hac.get('ci95_high_pct'))}] | "
                f"{fmt(hac.get('p_bh_q_value_family_9'), 3)} |"
            )
    lines += [
        "", "## Cost sensitivity (later-period, primary 3-session horizon)", "",
        "| Regime | Cost bps/side | Net mean % | Net excess vs EW % | Events |",
        "|---|---:|---:|---:|---:|",
    ]
    for regime in REGIMES:
        for cost in COSTS_BPS:
            cell = later["3"][regime]["costs"][str(cost)]
            net = cell.get("mean_net_return_pct")
            excess = cell.get("mean_net_excess_vs_equal_weight_pct")
            lines.append(
                f"| {regime} | {cost} | {fmt(net)} | {fmt(excess)} | {cell['n_events']} |"
            )
    lines += [
        "", "## Interpretation limits", "",
        "- Returns overlap across daily signal dates; HAC lag H-1 is used. No CAGR or Sharpe is reported.",
        "- Cost stress subtracts a simple round trip from each event; no portfolio turnover, market impact, or fill simulation.",
        "- Current-constituent history is survivorship-biased; 2024+ was previously explored and is not an untouched holdout.",
        "- This screen cannot approve a strategy. A positive event study would require a separate daily portfolio simulation and forward paper validation.",
        "- ETF mean reversion is not included: the four Trend V1 ETF price files are not tracked in the repository.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", required=True, help="current-universe stock OHLCV CSV")
    parser.add_argument("--spy", required=True, help="SPY benchmark OHLCV CSV")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args(argv)
    stock_path, spy_path = Path(args.stocks), Path(args.spy)
    stocks = pd.read_csv(stock_path, low_memory=False)
    spy = pd.read_csv(spy_path, low_memory=False)
    result = run_screen(stocks, spy)
    result["input_files"] = {
        "stocks": {"path": str(stock_path), "sha256": _sha256(stock_path), "bytes": stock_path.stat().st_size},
        "spy": {"path": str(spy_path), "sha256": _sha256(spy_path), "bytes": spy_path.stat().st_size},
    }
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path(args.markdown_out).write_text(render_report(result), encoding="utf-8")
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
