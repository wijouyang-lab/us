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


def _daily_metrics(frame: pd.DataFrame, factor: str, target: str, min_names: int):
    rows = []
    for date, group in frame.groupby("Snapshot_Date", sort=True):
        pair = group[[factor, target]].apply(pd.to_numeric, errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        if len(pair) < min_names or pair[factor].nunique() < 2:
            continue
        ic = pair[factor].corr(pair[target], method="spearman")
        if not np.isfinite(ic):
            continue
        pair = pair.assign(_q=pd.qcut(pair[factor].rank(method="first"), 5, labels=False) + 1)
        q5 = pair.loc[pair["_q"] == 5, target].mean()
        q1 = pair.loc[pair["_q"] == 1, target].mean()
        rows.append({"date": date, "ic": float(ic), "spread": float(q5 - q1), "n": len(pair)})
    return pd.DataFrame(rows)


def _summary(daily: pd.DataFrame, cost_bps: float):
    if daily.empty:
        return {"n_days": 0, "mean_daily_ic": None, "icir": None,
                "gross_q5_q1_spread": None, "net_q5_q1_spread": None,
                "positive_spread_day_pct": None}
    ic = daily["ic"].to_numpy(dtype=float)
    spread = daily["spread"].to_numpy(dtype=float)
    ic_std = float(np.std(ic, ddof=1)) if len(ic) > 1 else 0.0
    gross = float(np.mean(spread))
    # Approximation: one long and one short leg, each incurring one-way cost.
    net = gross - 2.0 * cost_bps / 10000.0
    return {
        "n_days": int(len(daily)),
        "n_stock_day_observations": int(daily["n"].sum()),
        "mean_daily_ic": round(float(np.mean(ic)), 6),
        "icir": round(float(np.mean(ic) / ic_std), 4) if ic_std > 0 else None,
        "gross_q5_q1_spread": round(gross, 6),
        "net_q5_q1_spread": round(net, 6),
        "positive_spread_day_pct": round(float(np.mean(spread > 0) * 100), 2),
    }


def run(input_path: str, output_dir: str, max_base_factors: int = 8,
        cost_bps: float = 5.0, min_names: int = 10):
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

    candidates, metadata = generate_formula_candidates(
        source, feature_cols, date_column="Snapshot_Date",
        max_base_factors=max_base_factors,
    )
    work = pd.concat([source[["Snapshot_Date"]].reset_index(drop=True),
                      candidates.reset_index(drop=True)], axis=1)
    out_rows = []
    for target in targets:
        for meta in metadata:
            name = meta["candidate"]
            evaluated = work[["Snapshot_Date", name]].copy()
            evaluated[target] = pd.to_numeric(source[target].values, errors="coerce")
            daily = _daily_metrics(evaluated, name, target, min_names)
            summary = _summary(daily, cost_bps)
            dates = sorted(daily["date"].dropna().unique()) if not daily.empty else []
            # Three chronological test folds. Embargo the first horizon trading
            # dates of folds 2/3 to reduce overlap from forward-return labels.
            fold_summaries = []
            horizon = int(target.upper().removeprefix("FORWARD_RETURN_").removesuffix("D"))
            if dates:
                chunks = [list(x) for x in np.array_split(np.array(dates, dtype="datetime64[ns]"), 3) if len(x)]
                for fold_no, chunk in enumerate(chunks, start=1):
                    allowed = set(pd.Timestamp(x) for x in chunk)
                    if fold_no > 1 and len(chunk) > horizon:
                        allowed = set(pd.Timestamp(x) for x in chunk[horizon:])
                    fold = daily[daily["date"].isin(allowed)]
                    fold_summaries.append({"fold": fold_no, **_summary(fold, cost_bps)})
            out_rows.append({
                "candidate": name, "formula": meta["formula"], "family": meta["family"],
                "horizon": target, **summary, "folds": fold_summaries,
            })

    # Correct approximate two-sided normal p-values for mean daily IC across the
    # full candidate family per horizon; these are diagnostics, not proof of alpha.
    for target in targets:
        idxs = [i for i, row in enumerate(out_rows) if row["horizon"] == target and row["n_days"] >= 10]
        pvals = []
        for i in idxs:
            row = out_rows[i]
            # Recover a conservative normal approximation from ICIR and n_days.
            z = abs(row["icir"] or 0.0) * math.sqrt(row["n_days"])
            pvals.append(math.erfc(z / math.sqrt(2.0)))
        qvals = _bh_qvalues(pvals)
        for i, q in zip(idxs, qvals):
            out_rows[i]["ic_fdr_q_value"] = round(q, 6)
        for i, row in enumerate(out_rows):
            if row["horizon"] == target and "ic_fdr_q_value" not in row:
                row["ic_fdr_q_value"] = None

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
            "base_feature_count": min(len(feature_cols), max_base_factors),
            "candidate_count": len(metadata),
            "cost_bps_per_leg": cost_bps,
            "warning": "Formula candidates are hypotheses. Cost-adjusted Q5-Q1 is approximate; no capacity, borrow, or full portfolio simulation is included.",
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
    args = parser.parse_args()
    if args.max_base_factors < 2 or args.min_names < 5 or args.cost_bps < 0:
        parser.error("max-base-factors >= 2, min-names >= 5, and cost-bps >= 0 are required")
    run(args.input, args.output_dir, args.max_base_factors, args.cost_bps, args.min_names)


if __name__ == "__main__":
    main()
