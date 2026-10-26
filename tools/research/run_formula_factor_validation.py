# -*- coding: utf-8 -*-
"""Research-only walk-forward evaluation for generated formula factors.

Input is an existing backtest/snapshot CSV containing point-in-time features and
Forward_Return_ND labels. This script writes only to the requested output path.
It never modifies production ranking or trading logic.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from formula_factor_discovery import generate_formula_candidates  # noqa: E402

ID_COLUMNS = {"Ticker", "Scan_Date", "Technical_Date", "Snapshot_Date", "schema_version", "Price"}
LABEL_PREFIXES = ("FORWARD_RETURN_", "WIN_")
LABEL_NAMES = {"TARGET", "LABEL", "OUTCOME"}


def _is_label(name: str) -> bool:
    upper = name.upper()
    return upper.startswith(LABEL_PREFIXES) or upper in LABEL_NAMES


def _bh_qvalues(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR q-values, preserving original order."""
    n = len(p_values)
    if not n:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    q = [1.0] * n
    running = 1.0
    for rank_index in range(n - 1, -1, -1):
        original = order[rank_index]
        rank = rank_index + 1
        running = min(running, p_values[original] * n / rank)
        q[original] = min(1.0, running)
    return q


def _winsorize_target_by_date(frame: pd.DataFrame, target: str,
                               lower_quantile: float = 0.01,
                               upper_quantile: float = 0.99) -> pd.Series:
    """Return a cross-sectionally winsorized copy of a forward-return label.

    This is a sensitivity analysis only; the original target column is never
    modified. Each date is clipped independently so one event-driven outlier
    does not set bounds for every other date.
    """
    if not 0 <= lower_quantile < upper_quantile <= 1:
        raise ValueError("winsorization quantiles must satisfy 0 <= lower < upper <= 1")
    if "Snapshot_Date" not in frame or target not in frame:
        raise ValueError("frame must contain Snapshot_Date and the requested target")
    values = pd.to_numeric(frame[target], errors="coerce").replace([np.inf, -np.inf], np.nan).copy()
    for indices in frame.groupby("Snapshot_Date", sort=False).groups.values():
        idx = list(indices)
        valid = values.loc[idx].dropna()
        if len(valid) < 10:
            continue
        lower = float(valid.quantile(lower_quantile))
        upper = float(valid.quantile(upper_quantile))
        values.loc[idx] = values.loc[idx].clip(lower=lower, upper=upper)
    return values


def _daily_metrics(frame: pd.DataFrame, factor: str, target: str, min_names: int):
    rows = []
    for date, group in frame.groupby("Snapshot_Date", sort=True):
        pair = group[[factor, target]].apply(pd.to_numeric, errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        has_tickers = "Ticker" in group.columns
        if has_tickers:
            pair["_ticker"] = group.loc[pair.index, "Ticker"].astype(str)
        if len(pair) < min_names or pair[factor].nunique() < 2:
            continue
        ic = pair[factor].corr(pair[target], method="spearman")
        if not np.isfinite(ic):
            continue
        pair = pair.assign(_q=pd.qcut(pair[factor].rank(method="first"), 5, labels=False) + 1)
        q5_rows = pair.loc[pair["_q"] == 5]
        q1_rows = pair.loc[pair["_q"] == 1]
        rows.append({
            "date": date,
            "ic": float(ic),
            "spread": float(q5_rows[target].mean() - q1_rows[target].mean()),
            "n": len(pair),
            "long_names": tuple(q5_rows["_ticker"].tolist()) if has_tickers else None,
            "short_names": tuple(q1_rows["_ticker"].tolist()) if has_tickers else None,
            "duplicate_tickers": bool(pair["_ticker"].duplicated().any()) if has_tickers else False,
        })
    return pd.DataFrame(rows)


def _portfolio_one_way_turnover(previous: tuple[str, ...] | None,
                                current: tuple[str, ...]) -> float:
    """Half-L1 weight change for an equal-weight leg, from 0 to 100% turnover."""
    if not current:
        return float("nan")
    current_names = set(current)
    if previous is None:
        # Initial establishment of a fully invested long/short leg.
        return 1.0
    previous_names = set(previous)
    if not previous_names:
        return 1.0
    old_weights = {name: 1.0 / len(previous_names) for name in previous_names}
    new_weights = {name: 1.0 / len(current_names) for name in current_names}
    return 0.5 * sum(
        abs(new_weights.get(name, 0.0) - old_weights.get(name, 0.0))
        for name in old_weights.keys() | new_weights.keys()
    )


def _attach_turnover_costs(daily: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Attach estimated one-way turnover and net spread; never changes source labels."""
    result = daily.copy()
    for col in ("long_turnover", "short_turnover", "total_turnover",
                "turnover_cost_bps", "turnover_aware_spread"):
        result[col] = np.nan
    result["turnover_cost_available"] = False
    required = {"long_names", "short_names", "duplicate_tickers", "spread"}
    if daily.empty or not required.issubset(daily.columns):
        return result
    if daily["duplicate_tickers"].fillna(True).astype(bool).any():
        # Do not claim executable turnover when duplicate date/ticker rows make
        # portfolio weights ambiguous. The raw cross-sectional metrics remain.
        return result
    if daily["long_names"].isna().any() or daily["short_names"].isna().any():
        return result

    previous_long = None
    previous_short = None
    for idx, row in result.sort_values("date").iterrows():
        long_names = tuple(row["long_names"])
        short_names = tuple(row["short_names"])
        long_turnover = _portfolio_one_way_turnover(previous_long, long_names)
        short_turnover = _portfolio_one_way_turnover(previous_short, short_names)
        total_turnover = long_turnover + short_turnover
        cost = total_turnover * float(cost_bps)
        result.loc[idx, "long_turnover"] = long_turnover
        result.loc[idx, "short_turnover"] = short_turnover
        result.loc[idx, "total_turnover"] = total_turnover
        result.loc[idx, "turnover_cost_bps"] = cost
        result.loc[idx, "turnover_aware_spread"] = float(row["spread"]) - cost / 10000.0
        result.loc[idx, "turnover_cost_available"] = True
        previous_long, previous_short = long_names, short_names
    return result


def _hac_mean_test(daily: pd.DataFrame, metric: str, max_lag: int) -> tuple[float | None, float | None]:
    """Newey-West HAC test for a daily metric mean; normal approximation for p-value.

    The test can be applied to both daily IC and the daily Q5-Q1 return spread.
    Overlapping forward-return labels induce serial dependence, so an IID standard
    error is not appropriate. This is still an approximation, not a proof of alpha.
    """
    if metric not in daily.columns:
        raise ValueError(f"missing HAC metric column: {metric}")
    values = pd.to_numeric(daily[metric], errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 10:
        return None, None
    mean = float(values.mean())
    centered = values - mean
    lag_max = min(max(int(max_lag), 0), n - 1)
    long_run_var = float(np.dot(centered, centered) / n)
    for lag in range(1, lag_max + 1):
        weight = 1.0 - lag / (lag_max + 1.0)
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / n)
        long_run_var += 2.0 * weight * covariance
    if not np.isfinite(long_run_var) or long_run_var <= 0:
        return None, None
    t_stat = mean / math.sqrt(long_run_var / n)
    p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
    return float(t_stat), float(min(1.0, max(0.0, p_value)))


def _hac_ic_test(daily: pd.DataFrame, max_lag: int) -> tuple[float | None, float | None]:
    """Backward-compatible wrapper for the mean daily IC HAC test."""
    return _hac_mean_test(daily, "ic", max_lag)

def _summary(daily: pd.DataFrame, cost_bps: float):
    empty_turnover = {
        "turnover_cost_available": False,
        "mean_long_turnover": None, "mean_short_turnover": None,
        "mean_total_turnover": None, "mean_turnover_cost_bps": None,
        "turnover_aware_net_q5_q1_spread": None,
        "turnover_aware_positive_spread_day_pct": None,
    }
    if daily.empty:
        return {
            "n_days": 0, "mean_daily_ic": None, "icir": None,
            "gross_q5_q1_spread": None, "net_q5_q1_spread": None,
            "positive_spread_day_pct": None, **empty_turnover,
        }
    ic = daily["ic"].to_numpy(dtype=float)
    spread = daily["spread"].to_numpy(dtype=float)
    ic_std = float(np.std(ic, ddof=1)) if len(ic) > 1 else 0.0
    gross = float(np.mean(spread))
    # Preserve the prior fixed-cost estimate so existing reports remain comparable.
    net = gross - 2.0 * cost_bps / 10000.0
    result = {
        "n_days": int(len(daily)),
        "n_stock_day_observations": int(daily["n"].sum()),
        "mean_daily_ic": round(float(np.mean(ic)), 6),
        "icir": round(float(np.mean(ic) / ic_std), 4) if ic_std > 0 else None,
        "gross_q5_q1_spread": round(gross, 6),
        "net_q5_q1_spread": round(net, 6),
        "positive_spread_day_pct": round(float(np.mean(spread > 0) * 100), 2),
        **empty_turnover,
    }
    available = (
        "turnover_aware_spread" in daily
        and "turnover_cost_available" in daily
        and daily["turnover_cost_available"].astype(bool).all()
    )
    if available:
        turnover_spread = pd.to_numeric(daily["turnover_aware_spread"], errors="coerce").to_numpy(dtype=float)
        if len(turnover_spread) and np.isfinite(turnover_spread).all():
            result.update({
                "turnover_cost_available": True,
                "mean_long_turnover": round(float(daily["long_turnover"].mean()), 6),
                "mean_short_turnover": round(float(daily["short_turnover"].mean()), 6),
                "mean_total_turnover": round(float(daily["total_turnover"].mean()), 6),
                "mean_turnover_cost_bps": round(float(daily["turnover_cost_bps"].mean()), 6),
                "turnover_aware_net_q5_q1_spread": round(float(np.mean(turnover_spread)), 6),
                "turnover_aware_positive_spread_day_pct": round(float(np.mean(turnover_spread > 0) * 100), 2),
            })
    return result


def run(input_path: str, output_dir: str, max_base_factors: int = 8,
        cost_bps: float = 5.0, min_names: int = 10,
        requested_factors: list[str] | None = None):
    source = pd.read_csv(input_path)
    date_col = next((c for c in ("Snapshot_Date", "Technical_Date", "Scan_Date") if c in source), None)
    if date_col is None:
        raise ValueError("input must contain Snapshot_Date, Technical_Date, or Scan_Date")
    source = source.copy()
    source["Snapshot_Date"] = pd.to_datetime(source[date_col], errors="coerce").dt.normalize()
    source = source.dropna(subset=["Snapshot_Date"])
    targets = [c for c in source.columns if c.upper().startswith("FORWARD_RETURN_")]
    if not targets:
        raise ValueError("input contains no Forward_Return_ND label columns")
    feature_cols = []
    for col in source.columns:
        if col in ID_COLUMNS or col == "Snapshot_Date" or _is_label(col):
            continue
        numeric = pd.to_numeric(source[col], errors="coerce")
        if numeric.notna().sum() >= min_names and numeric.nunique(dropna=True) > 1:
            feature_cols.append(col)
    if not feature_cols:
        raise ValueError("no numeric feature columns available after label/metadata exclusion")

    # Explicitly requested factors take precedence over CSV column order. This is
    # important because a capped search must not silently omit known baselines
    # (e.g. ATR_Pct) merely because they occur later in a wide CSV.
    requested_factors = requested_factors or []
    prioritized = [c for c in dict.fromkeys(requested_factors) if c in feature_cols]
    selected = prioritized + [c for c in feature_cols if c not in prioritized]
    selected = selected[:max_base_factors]
    candidates, metadata = generate_formula_candidates(
        source, selected, date_column="Snapshot_Date",
        max_base_factors=max_base_factors,
    )
    work = pd.concat([source[["Snapshot_Date", "Ticker"]].reset_index(drop=True),
                      candidates.reset_index(drop=True)], axis=1)
    # Keep the raw labels as the primary analysis. A separate per-date
    # winsorized sensitivity reveals whether results depend on a tiny number of
    # extreme outcomes; it is not a replacement for genuine event returns.
    target_frame = pd.DataFrame({
        "Snapshot_Date": source["Snapshot_Date"].reset_index(drop=True),
    })
    winsorized_targets = {}
    for target in targets:
        target_frame[target] = pd.to_numeric(source[target].values, errors="coerce")
        winsorized_targets[target] = _winsorize_target_by_date(target_frame, target)
    out_rows = []
    for target in targets:
        for meta in metadata:
            name = meta["candidate"]
            evaluated = work[["Snapshot_Date", "Ticker", name]].copy()
            evaluated[target] = pd.to_numeric(source[target].values, errors="coerce")
            daily = _attach_turnover_costs(
                _daily_metrics(evaluated, name, target, min_names), cost_bps
            )
            horizon = int(target.upper().removeprefix("FORWARD_RETURN_").removesuffix("D"))
            summary = _summary(daily, cost_bps)
            winsorized_eval = work[["Snapshot_Date", "Ticker", name]].copy()
            winsorized_eval[target] = winsorized_targets[target].to_numpy()
            winsorized_daily = _attach_turnover_costs(
                _daily_metrics(winsorized_eval, name, target, min_names), cost_bps
            )
            winsorized_summary = _summary(winsorized_daily, cost_bps)
            for key, value in winsorized_summary.items():
                summary[f"winsorized_{key}"] = value
            winsorized_ic_t, winsorized_ic_p = _hac_mean_test(
                winsorized_daily, "ic", max_lag=horizon - 1
            )
            winsorized_spread_t, winsorized_spread_p = _hac_mean_test(
                winsorized_daily, "spread", max_lag=horizon - 1
            )
            summary["winsorized_ic_hac_t"] = round(winsorized_ic_t, 4) if winsorized_ic_t is not None else None
            summary["winsorized_ic_hac_p_value"] = round(winsorized_ic_p, 8) if winsorized_ic_p is not None else None
            summary["winsorized_spread_hac_t"] = round(winsorized_spread_t, 4) if winsorized_spread_t is not None else None
            summary["winsorized_spread_hac_p_value"] = round(winsorized_spread_p, 8) if winsorized_spread_p is not None else None
            turnover_spread_t, turnover_spread_p = _hac_mean_test(
                daily, "turnover_aware_spread", max_lag=horizon - 1
            )
            winsorized_turnover_spread_t, winsorized_turnover_spread_p = _hac_mean_test(
                winsorized_daily, "turnover_aware_spread", max_lag=horizon - 1
            )
            summary["turnover_aware_spread_hac_t"] = round(turnover_spread_t, 4) if turnover_spread_t is not None else None
            summary["turnover_aware_spread_hac_p_value"] = round(turnover_spread_p, 8) if turnover_spread_p is not None else None
            summary["winsorized_turnover_aware_spread_hac_t"] = round(winsorized_turnover_spread_t, 4) if winsorized_turnover_spread_t is not None else None
            summary["winsorized_turnover_aware_spread_hac_p_value"] = round(winsorized_turnover_spread_p, 8) if winsorized_turnover_spread_p is not None else None
            hac_t, hac_p = _hac_mean_test(daily, "ic", max_lag=horizon - 1)
            spread_hac_t, spread_hac_p = _hac_mean_test(daily, "spread", max_lag=horizon - 1)
            summary["ic_hac_t"] = round(hac_t, 4) if hac_t is not None else None
            summary["ic_hac_p_value"] = round(hac_p, 8) if hac_p is not None else None
            summary["spread_hac_t"] = round(spread_hac_t, 4) if spread_hac_t is not None else None
            summary["spread_hac_p_value"] = round(spread_hac_p, 8) if spread_hac_p is not None else None
            summary["hac_lag_days"] = min(horizon - 1, max(len(daily) - 1, 0))
            dates = sorted(daily["date"].dropna().unique()) if not daily.empty else []
            # Three chronological test folds. Embargo the first horizon trading
            # dates of folds 2/3 to reduce overlap from forward-return labels.
            fold_summaries = []
            if dates:
                chunks = [list(x) for x in np.array_split(np.array(dates, dtype="datetime64[ns]"), 3) if len(x)]
                for fold_no, chunk in enumerate(chunks, start=1):
                    allowed = set(pd.Timestamp(x) for x in chunk)
                    if fold_no > 1:
                        # Always apply the embargo. If a fold is no longer than
                        # the label horizon, it has no independent dates left and
                        # must report zero observations rather than skip the purge.
                        allowed = set(pd.Timestamp(x) for x in chunk[horizon:])
                    fold = _attach_turnover_costs(daily[daily["date"].isin(allowed)], cost_bps)
                    fold_summaries.append({"fold": fold_no, **_summary(fold, cost_bps)})
            out_rows.append({
                "candidate": name, "formula": meta["formula"], "family": meta["family"],
                "horizon": target, **summary, "folds": fold_summaries,
            })

    # Correct each metric family separately within each horizon. Testing IC alone
    # cannot establish that the portfolio-like Q5-Q1 spread is statistically nonzero.
    for target in targets:
        for metric, p_column, q_column in (
            ("ic", "ic_hac_p_value", "ic_fdr_q_value"),
            ("spread", "spread_hac_p_value", "spread_fdr_q_value"),
            ("winsorized_ic", "winsorized_ic_hac_p_value", "winsorized_ic_fdr_q_value"),
            ("winsorized_spread", "winsorized_spread_hac_p_value", "winsorized_spread_fdr_q_value"),
            ("turnover_aware_spread", "turnover_aware_spread_hac_p_value", "turnover_aware_spread_fdr_q_value"),
            ("winsorized_turnover_aware_spread", "winsorized_turnover_aware_spread_hac_p_value", "winsorized_turnover_aware_spread_fdr_q_value"),
        ):
            idxs = [
                i for i, row in enumerate(out_rows)
                if row["horizon"] == target and row.get(p_column) is not None
            ]
            pvals = [float(out_rows[i][p_column]) for i in idxs]
            qvals = _bh_qvalues(pvals)
            for i, q in zip(idxs, qvals):
                out_rows[i][q_column] = round(q, 8)
            for i, row in enumerate(out_rows):
                if row["horizon"] == target and q_column not in row:
                    row[q_column] = None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    flat = [{k: v for k, v in row.items() if k != "folds"} for row in out_rows]
    pd.DataFrame(flat).to_csv(out / "formula_factor_metrics.csv", index=False)
    (out / "formula_factor_report.json").write_text(
        json.dumps({
            "research_only": True,
            "input": str(Path(input_path)),
            "rows": int(len(source)),
            "date_min": str(source["Snapshot_Date"].min().date()) if len(source) else None,
            "date_max": str(source["Snapshot_Date"].max().date()) if len(source) else None,
            "available_numeric_feature_count": len(feature_cols),
            "selected_base_features": selected,
            "candidate_count": len(metadata),
            "cost_bps_per_leg": cost_bps,
            "inference_method": "Newey-West HAC tests for mean daily IC and mean daily Q5-Q1 spread with lag horizon-1; separate Benjamini-Hochberg FDR families within each horizon; two-sided normal approximation.",
            "warning": "Formula candidates are hypotheses. HAC reduces but does not eliminate dependence from overlapping labels. Cost-adjusted Q5-Q1 is approximate; no capacity, borrow, turnover-aware cost, or full portfolio simulation is included. Per-date 1st/99th percentile winsorized metrics are a tail-sensitivity check only; raw results remain primary and genuine event returns are not deleted. Turnover-aware net spread estimates equal-weighted top/bottom quintile portfolio turnover and one-way costs; it is a simplified diagnostic, not a full execution simulation.",
            "results": out_rows,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"formula candidates={len(metadata)}; horizons={len(targets)}; rows={len(source)}")
    print(f"wrote {out / 'formula_factor_metrics.csv'} and {out / 'formula_factor_report.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Existing snapshot/backtest CSV with forward-return labels")
    parser.add_argument("--output-dir", required=True, help="Output directory (created if absent)")
    parser.add_argument("--max-base-factors", type=int, default=8)
    parser.add_argument("--cost-bps", type=float, default=5.0, help="One-way cost in basis points per leg")
    parser.add_argument("--min-names", type=int, default=10)
    parser.add_argument(
        "--factor-columns", default="",
        help="Comma-separated priority list; available columns are selected first before the cap",
    )
    args = parser.parse_args()
    if args.max_base_factors < 2 or args.min_names < 5 or args.cost_bps < 0:
        parser.error("max-base-factors >= 2, min-names >= 5, and cost-bps >= 0 are required")
    requested = [x.strip() for x in args.factor_columns.split(",") if x.strip()]
    run(args.input, args.output_dir, args.max_base_factors, args.cost_bps, args.min_names, requested)


if __name__ == "__main__":
    main()
