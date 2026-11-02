#!/usr/bin/env python3
"""Per-ETF short-horizon reversal event study using provider-adjusted total returns.

This is a research-only time-series event study, not a portfolio backtest.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ("GLD", "IWM", "QQQ", "TLT", "BIL", "SGOV", "SHV")
HORIZONS = (1, 3, 5)
REGIMES = ("RISK_ON", "RISK_OFF", "TRANSITION")
COSTS_BPS_PER_SIDE = (5, 10, 20, 50)
LOOKBACK = 252
TAIL_QUANTILE = 0.05
HAC_LAG = 20


def _load_frame(frame: pd.DataFrame, name: str, require_actions: bool = True) -> pd.DataFrame:
    required = {"Date", "Open", "Close", "Adj Close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")
    d = frame.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce").dt.normalize()
    for col in ("Open", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"):
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date", "Open", "Close", "Adj Close"])
    d = d[(d["Open"] > 0) & (d["Close"] > 0) & (d["Adj Close"] > 0)]
    if d["Date"].duplicated().any():
        raise ValueError(f"{name}: duplicate dates")
    if require_actions:
        for col in ("Dividends", "Stock Splits"):
            if col not in d:
                d[col] = 0.0
    return d.sort_values("Date").set_index("Date")


def _market_frame(spy: pd.DataFrame) -> pd.DataFrame:
    s = _load_frame(spy, "SPY")
    s["MA200"] = s["Close"].rolling(200, min_periods=200).mean()
    s["MA200_Slope20"] = s["MA200"] / s["MA200"].shift(20) - 1.0
    risk_on = (s["Close"] > s["MA200"]) & (s["MA200_Slope20"] > 0)
    risk_off = (s["Close"] < s["MA200"]) & (s["MA200_Slope20"] < 0)
    s["Regime"] = np.select(
        [risk_on.fillna(False), risk_off.fillna(False)],
        ["RISK_ON", "RISK_OFF"],
        default="TRANSITION",
    )
    return s


def hac_dummy_effect(returns: np.ndarray, event_mask: np.ndarray, max_lag: int = HAC_LAG) -> dict:
    """Newey-West OLS event-dummy effect: mean(event) minus mean(non-event).

    The panel is a daily sequence. A 20-session HAC lag is predeclared to cover
    short holding-window overlap and clustering of extreme-return events.
    P-values use a normal approximation and remain descriptive.
    """
    y = np.asarray(returns, dtype=float)
    e = np.asarray(event_mask, dtype=float)
    valid = np.isfinite(y) & np.isfinite(e)
    y, e = y[valid], e[valid]
    n = int(len(y))
    event_n = int(e.sum())
    if n < 100 or event_n < 10 or event_n >= n - 10:
        return {
            "n_daily_observations": n, "n_event_observations": event_n,
            "effect": None, "se_hac": None, "t_hac": None,
            "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None,
            "status": "INSUFFICIENT_DATA",
        }
    x = np.column_stack([np.ones(n), e])
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ (x.T @ y)
    residual = y - x @ beta
    scores = x * residual[:, None]
    meat = scores.T @ scores
    lag_limit = min(max(0, int(max_lag)), n - 1)
    for lag in range(1, lag_limit + 1):
        weight = 1.0 - lag / (lag_limit + 1.0)
        gamma = scores[lag:].T @ scores[:-lag]
        meat += weight * (gamma + gamma.T)
    covariance = xtx_inv @ meat @ xtx_inv
    variance = float(covariance[1, 1])
    if not math.isfinite(variance) or variance <= 0:
        return {
            "n_daily_observations": n, "n_event_observations": event_n,
            "effect": float(beta[1]), "se_hac": None, "t_hac": None,
            "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None,
            "status": "NON_POSITIVE_HAC_VARIANCE",
        }
    se = math.sqrt(variance)
    t_stat = float(beta[1] / se)
    p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
    return {
        "n_daily_observations": n,
        "n_event_observations": event_n,
        "effect": float(beta[1]),
        "se_hac": se,
        "t_hac": t_stat,
        "p_two_sided_normal": p_value,
        "ci95_low": float(beta[1] - 1.96 * se),
        "ci95_high": float(beta[1] + 1.96 * se),
        "status": "DESCRIPTIVE_HAC_OLS",
    }


def benjamini_hochberg(p_values: dict[str, float | None]) -> dict[str, float | None]:
    valid = [(key, float(value)) for key, value in p_values.items()
             if value is not None and math.isfinite(float(value))]
    valid.sort(key=lambda item: item[1])
    adjusted: dict[str, float | None] = {key: None for key in p_values}
    m, running = len(valid), 1.0
    for rank in range(m, 0, -1):
        key, p_value = valid[rank - 1]
        running = min(running, p_value * m / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


def _make_series(frame: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    name = str(frame["Ticker"].iloc[0]) if "Ticker" in frame and len(frame) else "ETF"
    d = _load_frame(frame, name)
    d = d.reindex(calendar)
    d["AdjFactor"] = d["Adj Close"] / d["Close"]
    d["AdjOpen"] = d["Open"] * d["AdjFactor"]
    d["Ret5_Total"] = d["Adj Close"].pct_change(5, fill_method=None)
    # At t, this threshold contains only the preceding 252 completed returns.
    d["TailThreshold"] = (
        d["Ret5_Total"].rolling(LOOKBACK, min_periods=LOOKBACK)
        .quantile(TAIL_QUANTILE).shift(1)
    )
    d["Event"] = (d["Ret5_Total"] <= d["TailThreshold"]) & d["TailThreshold"].notna()
    return d


def _non_overlapping_count(session_indices: list[int], horizon: int) -> int:
    count = 0
    next_allowed = -10**12
    for index in sorted(session_indices):
        if index >= next_allowed:
            count += 1
            next_allowed = index + horizon
    return count


def build_etf_screen(etf_frames: dict[str, pd.DataFrame], spy: pd.DataFrame) -> dict:
    """Vectorized per-ETF event screen on the exact SPY trading-session calendar."""
    market = _market_frame(spy)
    calendar = pd.DatetimeIndex(market.index)
    if len(calendar) < 300:
        raise ValueError("SPY calendar must contain at least 300 sessions")
    series = {ticker: _make_series(frame, calendar) for ticker, frame in etf_frames.items()}
    if "BIL" not in series:
        raise ValueError("BIL is required as the short-Treasury comparison proxy")
    spy_series = _make_series(spy.assign(Ticker="SPY"), calendar)
    bil = series["BIL"]
    spy_adj_open = spy_series["AdjOpen"].to_numpy(dtype=float)
    regime_array = market["Regime"].astype(str).to_numpy()
    outputs: dict[str, dict] = {}
    all_p: dict[str, float | None] = {}

    for ticker, asset in series.items():
        outputs[ticker] = {"data": {}, "horizons": {}}
        outputs[ticker]["data"] = {
            "first_date": asset["Close"].first_valid_index().date().isoformat()
                if asset["Close"].notna().any() else None,
            "last_date": asset["Close"].last_valid_index().date().isoformat()
                if asset["Close"].notna().any() else None,
            "sessions": int(asset["Close"].notna().sum()),
            "dividend_event_rows": int(asset.get("Dividends", pd.Series(0, index=asset.index)).fillna(0).ne(0).sum()),
            "split_event_rows": int(asset.get("Stock Splits", pd.Series(0, index=asset.index)).fillna(0).ne(0).sum()),
        }

        threshold_valid = asset["TailThreshold"].notna().to_numpy(dtype=bool)
        event_flags = asset["Event"].fillna(False).to_numpy(dtype=bool)
        raw_open = asset["Open"].to_numpy(dtype=float)
        adjusted_open = asset["AdjOpen"].to_numpy(dtype=float)
        bil_adjusted_open = bil["AdjOpen"].to_numpy(dtype=float)

        for horizon in HORIZONS:
            n = len(calendar)
            signal_indices = np.arange(0, max(0, n - horizon - 1), dtype=int)
            entry_indices = signal_indices + 1
            exit_indices = signal_indices + 1 + horizon

            valid = threshold_valid[signal_indices]
            valid &= np.isfinite(raw_open[entry_indices]) & (raw_open[entry_indices] > 0)
            valid &= np.isfinite(raw_open[exit_indices]) & (raw_open[exit_indices] > 0)
            valid &= np.isfinite(adjusted_open[entry_indices]) & (adjusted_open[entry_indices] > 0)
            valid &= np.isfinite(adjusted_open[exit_indices]) & (adjusted_open[exit_indices] > 0)
            valid &= np.isfinite(spy_adj_open[entry_indices]) & (spy_adj_open[entry_indices] > 0)
            valid &= np.isfinite(spy_adj_open[exit_indices]) & (spy_adj_open[exit_indices] > 0)

            event_candidates = threshold_valid[signal_indices] & event_flags[signal_indices]
            missing_execution_events = int(np.sum(event_candidates & ~valid))
            selected_signals = signal_indices[valid]
            entry_valid = entry_indices[valid]
            exit_valid = exit_indices[valid]
            is_event = event_flags[selected_signals]

            if len(selected_signals) == 0:
                outputs[ticker]["horizons"][str(horizon)] = {
                    "status": "NO_USABLE_DAILY_OBSERVATIONS", "n_daily_observations": 0,
                    "n_events": 0, "n_non_overlapping_events": 0,
                    "missing_execution_events": missing_execution_events,
                }
                all_p[f"{ticker}:H{horizon}"] = None
                continue

            total_return = adjusted_open[exit_valid] / adjusted_open[entry_valid] - 1.0
            price_return = raw_open[exit_valid] / raw_open[entry_valid] - 1.0
            spy_return = spy_adj_open[exit_valid] / spy_adj_open[entry_valid] - 1.0
            bil_entry, bil_exit = bil_adjusted_open[entry_valid], bil_adjusted_open[exit_valid]
            bil_return = np.full(len(selected_signals), np.nan, dtype=float)
            bil_valid = (
                np.isfinite(bil_entry) & (bil_entry > 0)
                & np.isfinite(bil_exit) & (bil_exit > 0)
            )
            bil_return[bil_valid] = bil_exit[bil_valid] / bil_entry[bil_valid] - 1.0

            daily = pd.DataFrame({
                "signal_date": calendar[selected_signals],
                "session_index": selected_signals,
                "regime": regime_array[selected_signals],
                "is_event": is_event,
                "total_return": total_return,
                "price_return": price_return,
                "spy_return": spy_return,
                "bil_return": bil_return,
            })
            events = daily.loc[daily["is_event"]].copy()
            effect = hac_dummy_effect(daily["total_return"].to_numpy(float), is_event, HAC_LAG)
            event_indices = events["session_index"].astype(int).tolist()

            event_total = events["total_return"].to_numpy(dtype=float)
            event_price = events["price_return"].to_numpy(dtype=float)
            event_spy = events["spy_return"].to_numpy(dtype=float)
            event_bil = events["bil_return"].to_numpy(dtype=float)
            bil_event_valid = np.isfinite(event_bil)

            cell = {
                "status": "EVENT_STUDY_NOT_STRATEGY_VALIDATION",
                "n_daily_observations": int(len(daily)),
                "n_events": int(len(events)),
                "n_non_overlapping_events": _non_overlapping_count(event_indices, horizon),
                "missing_execution_events": missing_execution_events,
                "mean_event_total_return_pct": float(np.mean(event_total) * 100) if len(event_total) else None,
                "median_event_total_return_pct": float(np.median(event_total) * 100) if len(event_total) else None,
                "mean_event_price_return_pct": float(np.mean(event_price) * 100) if len(event_price) else None,
                "win_rate_total_return_pct": float(np.mean(event_total > 0) * 100) if len(event_total) else None,
                "mean_event_excess_vs_spy_pct": float(np.mean(event_total - event_spy) * 100) if len(event_total) else None,
                "median_event_excess_vs_spy_pct": float(np.median(event_total - event_spy) * 100) if len(event_total) else None,
                "mean_event_excess_vs_bil_pct": (
                    float(np.mean(event_total[bil_event_valid] - event_bil[bil_event_valid]) * 100)
                    if np.any(bil_event_valid) else None
                ),
                "event_effect_vs_non_event_total_return": {
                    **effect,
                    "effect_pct": None if effect["effect"] is None else effect["effect"] * 100,
                    "se_pct": None if effect["se_hac"] is None else effect["se_hac"] * 100,
                    "ci95_low_pct": None if effect["ci95_low"] is None else effect["ci95_low"] * 100,
                    "ci95_high_pct": None if effect["ci95_high"] is None else effect["ci95_high"] * 100,
                    "hac_lag_sessions": HAC_LAG,
                },
                "regime_event_counts": {
                    regime: int((events["regime"] == regime).sum()) for regime in REGIMES
                },
                "regime_mean_total_return_pct": {
                    regime: (
                        float(events.loc[events["regime"] == regime, "total_return"].mean() * 100)
                        if (events["regime"] == regime).any() else None
                    ) for regime in REGIMES
                },
                "cost_sensitivity": {},
            }
            for cost in COSTS_BPS_PER_SIDE:
                net = event_total - 2.0 * cost / 10_000.0
                bil_excess = net[bil_event_valid] - event_bil[bil_event_valid]
                spy_excess = net - event_spy
                cell["cost_sensitivity"][str(cost)] = {
                    "cost_bps_per_side": cost,
                    "mean_net_return_pct": float(np.mean(net) * 100) if len(net) else None,
                    "median_net_return_pct": float(np.median(net) * 100) if len(net) else None,
                    "mean_net_excess_vs_spy_pct": float(np.mean(spy_excess) * 100) if len(net) else None,
                    "mean_net_excess_vs_bil_pct": float(np.mean(bil_excess) * 100) if len(bil_excess) else None,
                }

            all_p[f"{ticker}:H{horizon}"] = (
                effect["p_two_sided_normal"]
                if len(events) and effect["p_two_sided_normal"] is not None else None
            )
            outputs[ticker]["horizons"][str(horizon)] = cell

    q_values = benjamini_hochberg(all_p)
    for ticker in outputs:
        for horizon in HORIZONS:
            cell = outputs[ticker]["horizons"][str(horizon)]
            if "event_effect_vs_non_event_total_return" in cell:
                cell["event_effect_vs_non_event_total_return"]["p_bh_q_value_family_21"] = q_values[f"{ticker}:H{horizon}"]

    return {
        "status": "EXPLORATORY_ETF_TIME_SERIES_EVENT_STUDY",
        "data_source": "Yahoo Finance via yfinance; no API token",
        "symbols": list(etf_frames),
        "signal": "5-session total return <= prior 252-session 5th percentile, per ETF",
        "execution": "signal after close; next SPY session Open entry; exit after exact H further SPY sessions",
        "return_method": "adjusted_open = raw Open * (Adj Close / Close); provider-adjusted total-return proxy",
        "horizons_sessions": list(HORIZONS),
        "tail_quantile": TAIL_QUANTILE,
        "lookback_sessions": LOOKBACK,
        "hac_lag_sessions": HAC_LAG,
        "costs_bps_per_side": list(COSTS_BPS_PER_SIDE),
        "market_regime": {
            "RISK_ON": "SPY Close > MA200 and MA200 20-session slope > 0",
            "RISK_OFF": "SPY Close < MA200 and MA200 20-session slope < 0",
            "TRANSITION": "all other observations",
        },
        "limitations": [
            "Only currently existing funds are included; delisted and liquidated ETF history is not reconstructed.",
            "Yahoo Finance Adj Close is a provider-adjusted total-return proxy; verify corporate-action adjustments before any portfolio use.",
            "Event effects are estimated by a daily OLS event dummy with Newey-West HAC lag 20; normal-approximation p-values are descriptive.",
            "The 21 ETF-by-horizon tests use BH correction; this remains exploratory and cannot approve a strategy.",
            "Event returns overlap; report non-overlapping event counts separately.",
            "Cost stress subtracts a simple full-notional round trip and does not model spread, impact, capacity, or execution.",
        ],
        "multiple_testing": {
            "method": "Benjamini-Hochberg",
            "family": "7 ETFs x 3 horizons = 21 event-dummy effects",
            "raw_p_values": all_p,
            "q_values": q_values,
            "not_confirmatory": True,
        },
        "results": outputs,
    }

def render_report(result: dict) -> str:
    lines = [
        "# ETF Short-Term Reversal Screen (Research Only)", "",
        f"> Status: {result['status']}. Not a portfolio backtest or strategy approval.",
        f"> Signal: {result['signal']}.",
        f"> Total return proxy: {result['return_method']}.",
        f"> HAC: daily event-dummy OLS with {result['hac_lag_sessions']}-session Newey-West lag; BH across 21 tests.", "",
        "| ETF | Horizon | Events | Non-overlap | Mean event total % | Median event total % | Mean excess vs SPY % | Event effect vs non-event % | HAC t | BH q |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for ticker, item in result["results"].items():
        for horizon in HORIZONS:
            cell = item["horizons"][str(horizon)]
            effect = cell.get("event_effect_vs_non_event_total_return", {})
            def fmt(value):
                return "NA" if value is None else f"{value:+.3f}"
            lines.append(
                f"| {ticker} | {horizon} | {cell.get('n_events', 0)} | {cell.get('n_non_overlapping_events', 0)} | "
                f"{fmt(cell.get('mean_event_total_return_pct'))} | {fmt(cell.get('median_event_total_return_pct'))} | "
                f"{fmt(cell.get('mean_event_excess_vs_spy_pct'))} | {fmt(effect.get('effect_pct'))} | "
                f"{fmt(effect.get('t_hac'))} | {fmt(effect.get('p_bh_q_value_family_21'))} |"
            )
    lines += [
        "", "## Cost sensitivity (mean net event return, percent)", "",
        "| ETF | H | 5 bps/side | 10 bps/side | 20 bps/side | 50 bps/side |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ticker, item in result["results"].items():
        for horizon in HORIZONS:
            cell = item["horizons"][str(horizon)]
            costs = cell.get("cost_sensitivity", {})
            vals = [costs.get(str(bps), {}).get("mean_net_return_pct") for bps in COSTS_BPS_PER_SIDE]
            lines.append(
                f"| {ticker} | {horizon} | " +
                " | ".join("NA" if value is None else f"{value:+.3f}" for value in vals) + " |"
            )
    lines += [
        "", "## Limitations", "",
        "- Only surviving funds are included; closed/liquidated ETF history is missing.",
        "- Adjusted Open is a provider-adjusted proxy and must be independently verified before any portfolio use.",
        "- Event windows overlap. Non-overlap counts are provided; HAC uses a 20-session lag.",
        "- BH-adjusted p-values are descriptive only; the asset panel and hypothesis are exploratory.",
        "- A positive result requires separate execution-aware portfolio simulation and forward paper trading.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args(argv)
    input_dir = Path(args.input_dir)
    spy_path = input_dir / "SPY.csv"
    if not spy_path.exists():
        raise FileNotFoundError(f"missing SPY calendar file: {spy_path}")
    spy = pd.read_csv(spy_path, low_memory=False)
    etf_frames = {}
    for ticker in TICKERS:
        path = input_dir / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing ETF history: {path}")
        etf_frames[ticker] = pd.read_csv(path, low_memory=False)
    result = build_etf_screen(etf_frames, spy)
    result["data_manifest"] = str(input_dir.parent / "manifest.json")
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path(args.markdown_out).write_text(render_report(result), encoding="utf-8")
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
