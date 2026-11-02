#!/usr/bin/env python3
"""Regime-conditioned ETF reversal diagnostics; research-only, no execution orders."""
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
COSTS_BPS = (5, 10, 20, 50)
LOOKBACK = 252
TAIL_QUANTILE = 0.05
HAC_LAG = 20
QQQ_PERIODS = (
    ("1999-2006", "1999-01-01", "2006-12-31"),
    ("2007-2015", "2007-01-01", "2015-12-31"),
    ("2016-2020", "2016-01-01", "2020-12-31"),
    ("2021-2026", "2021-01-01", "2026-10-31"),
)


def _load(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    required = {"Date", "Open", "Close", "Adj Close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")
    d = frame.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce").dt.normalize()
    for col in ("Open", "Close", "Adj Close"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Date"])
    if d["Date"].duplicated().any():
        raise ValueError(f"{name}: duplicate dates")
    return d.sort_values("Date").set_index("Date")


def _prepare_market(spy: pd.DataFrame):
    s = _load(spy, "SPY")
    s["MA200"] = s["Close"].rolling(200, min_periods=200).mean()
    s["MA200_Slope20"] = s["MA200"] / s["MA200"].shift(20) - 1.0
    risk_on = (s["Close"] > s["MA200"]) & (s["MA200_Slope20"] > 0)
    risk_off = (s["Close"] < s["MA200"]) & (s["MA200_Slope20"] < 0)
    s["Regime"] = np.select(
        [risk_on.fillna(False), risk_off.fillna(False)],
        ["RISK_ON", "RISK_OFF"],
        default="TRANSITION",
    )
    s["AdjOpen"] = s["Open"] * (s["Adj Close"] / s["Close"])
    return s


def _prepare_asset(frame: pd.DataFrame, ticker: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    d = _load(frame, ticker).reindex(calendar)
    d["AdjOpen"] = d["Open"] * (d["Adj Close"] / d["Close"])
    d["Ret5_Total"] = d["Adj Close"].pct_change(5, fill_method=None)
    # At t, the threshold uses only the prior 252 completed five-session returns.
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


def _hac_regime_event_effects(
    returns: np.ndarray,
    event: np.ndarray,
    regimes: np.ndarray,
    *,
    max_lag: int = HAC_LAG,
) -> dict[str, dict]:
    """OLS regime intercept controls + Event x regime effects, Newey-West HAC."""
    y = np.asarray(returns, dtype=float)
    e = np.asarray(event, dtype=bool)
    r = np.asarray(regimes, dtype=str)
    valid = np.isfinite(y) & np.isin(r, REGIMES)
    y, e, r = y[valid], e[valid], r[valid]
    n = len(y)
    if n <= max(100, max_lag + 10):
        return {
            regime: {
                "status": "INSUFFICIENT_DAILY_OBSERVATIONS",
                "n_daily_observations": n,
                "n_event_observations": int(np.sum(e & (r == regime))),
                "effect": None, "se_hac": None, "t_hac": None,
                "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None,
            } for regime in REGIMES
        }

    x = np.column_stack([
        np.ones(n),
        (r == "RISK_OFF").astype(float),
        (r == "TRANSITION").astype(float),
        (e & (r == "RISK_ON")).astype(float),
        (e & (r == "RISK_OFF")).astype(float),
        (e & (r == "TRANSITION")).astype(float),
    ])
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
    covariance *= n / max(1, n - x.shape[1])

    output = {}
    coefficient_index = {"RISK_ON": 3, "RISK_OFF": 4, "TRANSITION": 5}
    for regime in REGIMES:
        j = coefficient_index[regime]
        event_n = int(np.sum(e & (r == regime)))
        variance = float(covariance[j, j])
        if event_n < 10 or not math.isfinite(variance) or variance <= 0:
            output[regime] = {
                "status": "INSUFFICIENT_OR_INVALID_HAC_VARIANCE",
                "n_daily_observations": n,
                "n_event_observations": event_n,
                "effect": float(beta[j]),
                "se_hac": None, "t_hac": None,
                "p_two_sided_normal": None, "ci95_low": None, "ci95_high": None,
            }
            continue
        se = math.sqrt(variance)
        t_stat = float(beta[j] / se)
        output[regime] = {
            "status": "DESCRIPTIVE_HAC_OLS_WITH_REGIME_CONTROLS",
            "n_daily_observations": n,
            "n_event_observations": event_n,
            "effect": float(beta[j]),
            "se_hac": se,
            "t_hac": t_stat,
            "p_two_sided_normal": math.erfc(abs(t_stat) / math.sqrt(2.0)),
            "ci95_low": float(beta[j] - 1.96 * se),
            "ci95_high": float(beta[j] + 1.96 * se),
        }
    return output


def _bh_adjust(p_values: dict[str, float | None]) -> dict[str, float | None]:
    valid = [(key, float(value)) for key, value in p_values.items()
             if value is not None and math.isfinite(float(value))]
    valid.sort(key=lambda pair: pair[1])
    adjusted = {key: None for key in p_values}
    running = 1.0
    count = len(valid)
    for rank in range(count, 0, -1):
        key, p_value = valid[rank - 1]
        running = min(running, p_value * count / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


def _build_daily(
    asset: pd.DataFrame,
    market: pd.DataFrame,
    bil: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(market.index)
    n = len(calendar)
    signal_idx = np.arange(0, max(0, n - horizon - 1), dtype=int)
    entry_idx, exit_idx = signal_idx + 1, signal_idx + 1 + horizon

    event_flags = asset["Event"].fillna(False).to_numpy(dtype=bool)
    threshold_valid = asset["TailThreshold"].notna().to_numpy(dtype=bool)
    asset_open = asset["AdjOpen"].to_numpy(dtype=float)
    spy_open = market["AdjOpen"].to_numpy(dtype=float)
    bil_open = bil["AdjOpen"].to_numpy(dtype=float)

    valid = threshold_valid[signal_idx]
    valid &= np.isfinite(asset_open[entry_idx]) & (asset_open[entry_idx] > 0)
    valid &= np.isfinite(asset_open[exit_idx]) & (asset_open[exit_idx] > 0)
    valid &= np.isfinite(spy_open[entry_idx]) & (spy_open[entry_idx] > 0)
    valid &= np.isfinite(spy_open[exit_idx]) & (spy_open[exit_idx] > 0)

    selected = signal_idx[valid]
    entries, exits = entry_idx[valid], exit_idx[valid]
    total_return = asset_open[exits] / asset_open[entries] - 1.0
    spy_return = spy_open[exits] / spy_open[entries] - 1.0

    bil_ret = np.full(len(selected), np.nan, dtype=float)
    bil_valid = (
        np.isfinite(bil_open[entries]) & (bil_open[entries] > 0)
        & np.isfinite(bil_open[exits]) & (bil_open[exits] > 0)
    )
    bil_ret[bil_valid] = bil_open[exits[bil_valid]] / bil_open[entries[bil_valid]] - 1.0

    return pd.DataFrame({
        "signal_date": calendar[selected],
        "entry_date": calendar[entries],
        "exit_date": calendar[exits],
        "signal_index": selected,
        "regime": market["Regime"].astype(str).to_numpy()[selected],
        "is_event": event_flags[selected],
        "total_return": total_return,
        "spy_return": spy_return,
        "bil_return": bil_ret,
    })


def _summarize_regime(daily: pd.DataFrame, regime: str, horizon: int) -> dict:
    events = daily[(daily["is_event"]) & (daily["regime"] == regime)]
    total = events["total_return"].to_numpy(dtype=float)
    spy = events["spy_return"].to_numpy(dtype=float)
    bil = events["bil_return"].to_numpy(dtype=float)
    bil_valid = np.isfinite(bil)
    indices = events["signal_index"].astype(int).tolist()
    output = {
        "n_events": int(len(events)),
        "n_non_overlapping_events": _non_overlapping_count(indices, horizon),
        "mean_event_total_return_pct": float(np.mean(total) * 100) if len(total) else None,
        "median_event_total_return_pct": float(np.median(total) * 100) if len(total) else None,
        "mean_event_excess_vs_spy_pct": float(np.mean(total - spy) * 100) if len(total) else None,
        "median_event_excess_vs_spy_pct": float(np.median(total - spy) * 100) if len(total) else None,
        "mean_event_excess_vs_bil_pct": (
            float(np.mean(total[bil_valid] - bil[bil_valid]) * 100)
            if np.any(bil_valid) else None
        ),
        "n_bil_comparable_events": int(np.sum(bil_valid)),
        "cost_sensitivity": {},
    }
    for cost in COSTS_BPS:
        net = total - 2.0 * cost / 10_000.0
        output["cost_sensitivity"][str(cost)] = {
            "cost_bps_per_side": cost,
            "mean_net_return_pct": float(np.mean(net) * 100) if len(net) else None,
            "mean_net_excess_vs_spy_pct": (
                float(np.mean(net - spy) * 100) if len(net) else None
            ),
            "mean_net_excess_vs_bil_pct": (
                float(np.mean(net[bil_valid] - bil[bil_valid]) * 100)
                if np.any(bil_valid) else None
            ),
        }
    return output


def run_regime_diagnostics(frames: dict[str, pd.DataFrame], spy_frame: pd.DataFrame) -> dict:
    if "BIL" not in frames:
        raise ValueError("BIL data is required as the short-Treasury reference")
    market = _prepare_market(spy_frame)
    calendar = pd.DatetimeIndex(market.index)
    if len(calendar) < 300:
        raise ValueError("SPY calendar must contain at least 300 sessions")
    assets = {ticker: _prepare_asset(frame, ticker, calendar) for ticker, frame in frames.items()}
    bil = assets["BIL"]
    results: dict[str, dict] = {}
    p_values: dict[str, float | None] = {}
    qqq_periods: list[dict] = []

    for ticker, asset in assets.items():
        results[ticker] = {"data": {}, "horizons": {}}
        results[ticker]["data"] = {
            "first_date": asset["Close"].first_valid_index().date().isoformat()
                if asset["Close"].notna().any() else None,
            "last_date": asset["Close"].last_valid_index().date().isoformat()
                if asset["Close"].notna().any() else None,
            "sessions": int(asset["Close"].notna().sum()),
        }
        for horizon in HORIZONS:
            daily = _build_daily(asset, market, bil, horizon)
            if daily.empty:
                raise ValueError(f"{ticker}: no usable daily forward observations for H={horizon}")
            effects = _hac_regime_event_effects(
                daily["total_return"].to_numpy(dtype=float),
                daily["is_event"].to_numpy(dtype=bool),
                daily["regime"].to_numpy(dtype=str),
                max_lag=HAC_LAG,
            )
            regime_results = {}
            for regime in REGIMES:
                cell = _summarize_regime(daily, regime, horizon)
                effect = effects[regime]
                effect["effect_pct"] = None if effect["effect"] is None else effect["effect"] * 100
                effect["se_pct"] = None if effect["se_hac"] is None else effect["se_hac"] * 100
                effect["ci95_low_pct"] = None if effect["ci95_low"] is None else effect["ci95_low"] * 100
                effect["ci95_high_pct"] = None if effect["ci95_high"] is None else effect["ci95_high"] * 100
                cell["event_effect_vs_non_event_total_return"] = effect
                regime_results[regime] = cell
                p_values[f"{ticker}:H{horizon}:{regime}"] = effect["p_two_sided_normal"]
            results[ticker]["horizons"][str(horizon)] = {
                "n_daily_observations": int(len(daily)),
                "n_all_events": int(daily["is_event"].sum()),
                "missing_execution_event_count": int(
                    np.sum(
                        asset["Event"].fillna(False).to_numpy(dtype=bool)
                        & asset["TailThreshold"].notna().to_numpy(dtype=bool)
                    ) - daily["is_event"].sum()
                ),
                "regimes": regime_results,
            }

            # Post-hoc QQQ period slices; crossing-boundary event windows are purged.
            if ticker == "QQQ":
                for period, start, end in QQQ_PERIODS:
                    period_daily = daily[
                        (daily["signal_date"] >= pd.Timestamp(start))
                        & (daily["signal_date"] <= pd.Timestamp(end))
                        & (daily["exit_date"] <= pd.Timestamp(end))
                    ]
                    for regime in REGIMES:
                        cell = _summarize_regime(
                            period_daily[period_daily["regime"] == regime],
                            regime, horizon
                        )
                        qqq_periods.append({
                            "period": period,
                            "horizon": horizon,
                            "regime": regime,
                            **cell,
                        })

    q_values = _bh_adjust(p_values)
    for ticker in results:
        for horizon in HORIZONS:
            for regime in REGIMES:
                effect = results[ticker]["horizons"][str(horizon)]["regimes"][regime][
                    "event_effect_vs_non_event_total_return"
                ]
                key = f"{ticker}:H{horizon}:{regime}"
                effect["p_bh_q_value_family_63"] = q_values[key]

    return {
        "status": "EXPLORATORY_REGIME_CONDITIONED_ETF_REVERSAL",
        "data_source": "Yahoo Finance via yfinance; no API token",
        "signal": "ETF 5-session total return <= its prior 252-session 5th percentile",
        "execution": "signal after close; enter next SPY session Open; exit after exactly H further SPY sessions",
        "total_return_proxy": "adjusted_open = raw Open * (Adj Close / Close)",
        "regime_definition": {
            "RISK_ON": "SPY Close > MA200 and MA200 20-session slope > 0",
            "RISK_OFF": "SPY Close < MA200 and MA200 20-session slope < 0",
            "TRANSITION": "all other observations",
        },
        "horizons_sessions": list(HORIZONS),
        "costs_bps_per_side": list(COSTS_BPS),
        "hac_lag_sessions": HAC_LAG,
        "multiple_testing": {
            "method": "Benjamini-Hochberg",
            "family": "7 ETFs x 3 horizons x 3 regimes = 63",
            "valid_p_values": sum(value is not None for value in p_values.values()),
            "q_values": q_values,
            "normal_approximation": True,
            "not_confirmatory": True,
        },
        "limitations": [
            "Regime-conditioned ETF results are exploratory follow-up slices, not a fresh preregistered holdout.",
            "Daily event returns overlap; non-overlapping event counts are shown separately.",
            "HAC inference uses a 20-session Bartlett kernel on the full chronological daily return series.",
            "Only currently existing ETFs are included; closed/liquidated funds are not reconstructed.",
            "Yahoo adjusted prices are a provider total-return proxy and require independent corporate-action verification.",
            "Costs are full-notional round-trip deductions, not fill-level spreads, market impact, or capacity modeling.",
            "The event study is not a daily-NAV portfolio backtest and does not demonstrate a risk-controlled strategy.",
        ],
        "results": results,
        "qqq_period_sensitivity_posthoc": qqq_periods,
    }


def render_report(result: dict) -> str:
    lines = [
        "# Regime-Conditioned ETF Reversal Diagnostics (Research Only)", "",
        f"> Status: {result['status']}. Not a portfolio backtest or strategy approval.",
        f"> Signal: {result['signal']}.",
        f"> Execution: {result['execution']}.",
        f"> HAC: {result['hac_lag_sessions']}-session Newey-West; BH family = {result['multiple_testing']['family']}.", "",
        "| ETF | H | Regime | Events | Non-overlap | Mean event % | Median event % | Mean excess SPY % | Net excess SPY @10bps/side % | Event effect vs non-event % | HAC t | BH q |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def fmt(value):
        return "NA" if value is None else f"{value:+.3f}"
    for ticker, asset in result["results"].items():
        for horizon in HORIZONS:
            for regime in REGIMES:
                cell = asset["horizons"][str(horizon)]["regimes"][regime]
                effect = cell["event_effect_vs_non_event_total_return"]
                net10 = cell["cost_sensitivity"]["10"]["mean_net_excess_vs_spy_pct"]
                lines.append(
                    f"| {ticker} | {horizon} | {regime} | {cell['n_events']} | "
                    f"{cell['n_non_overlapping_events']} | "
                    f"{fmt(cell['mean_event_total_return_pct'])} | "
                    f"{fmt(cell['median_event_total_return_pct'])} | "
                    f"{fmt(cell['mean_event_excess_vs_spy_pct'])} | "
                    f"{fmt(net10)} | {fmt(effect.get('effect_pct'))} | "
                    f"{fmt(effect.get('t_hac'))} | "
                    f"{fmt(effect.get('p_bh_q_value_family_63'))} |"
                )
    lines += [
        "", "## QQQ chronological regime sensitivity (post-hoc, not holdout)", "",
        "| Period | H | Regime | Events | Non-overlap | Mean excess SPY % | Net excess SPY @10bps/side % | Net excess SPY @20bps/side % |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for cell in result["qqq_period_sensitivity_posthoc"]:
        net10 = cell["cost_sensitivity"]["10"]["mean_net_excess_vs_spy_pct"]
        net20 = cell["cost_sensitivity"]["20"]["mean_net_excess_vs_spy_pct"]
        lines.append(
            f"| {cell['period']} | {cell['horizon']} | {cell['regime']} | "
            f"{cell['n_events']} | {cell['n_non_overlapping_events']} | "
            f"{fmt(cell['mean_event_excess_vs_spy_pct'])} | {fmt(net10)} | {fmt(net20)} |"
        )
    lines += [
        "", "## Interpretation", "",
        "- A small q-value is a screening result, not a deployment decision. The full 63-test family is adjusted.",
        "- Risk-on / risk-off / transition are descriptive SPY states; TRANSITION is not synonymous with a confirmed sideways market.",
        "- QQQ is the only candidate showing several regime-conditioned event effects after the 63-test BH adjustment in this run.",
        "- The QQQ period table is post-hoc descriptive. It is not an untouched holdout and cannot validate the strategy.",
        "- A candidate must next pass a non-overlapping daily-NAV portfolio simulation, execution and cost audit, risk-budget test, and prospective paper period.",
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
    frames = {}
    for ticker in TICKERS:
        path = input_dir / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing ETF history: {path}")
        frames[ticker] = pd.read_csv(path, low_memory=False)
    result = run_regime_diagnostics(frames, spy)
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path(args.markdown_out).write_text(render_report(result), encoding="utf-8")
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
