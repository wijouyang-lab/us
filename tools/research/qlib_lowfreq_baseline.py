#!/usr/bin/env python3
"""Qlib LinearModel baseline on the PIT 2-year snapshot, with a cost-aware
monthly long/short evaluation and an equal-weight benchmark.

Research only. No production imports or writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from qlib.contrib.model.linear import LinearModel
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP


FEATURES = [
    "Momentum_5D_Pct",
    "Momentum_20D_Pct",
    "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct",
    "Volume_Ratio_20D",
    "ZScore_20D",
    "Beta_60D_SPY",
    "Stock_RS_20D_vs_SPY",
    "RSI",
    "MA20",
    "MA50",
    "MA20_Slope_Pct_5D",
    "ATR_Pct",
    "MACD_HIST_LAST",
    "KDJ_J",
]
HORIZON = 20


def prepare(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["Date"] = pd.to_datetime(df["Technical_Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df = df.dropna(subset=["Date", "Ticker", "Price"]).sort_values(["Ticker", "Date"])
    for c in FEATURES:
        if c not in df.columns:
            raise SystemExit(f"missing feature {c}")
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["label"] = df.groupby("Ticker", sort=False)["Price"].shift(-HORIZON) / df["Price"] - 1
    df = df.dropna(subset=FEATURES + ["label"])
    return df


def to_handler(df: pd.DataFrame) -> DataHandlerLP:
    idx = pd.MultiIndex.from_frame(df[["Date", "Ticker"]].rename(columns={"Date": "datetime", "Ticker": "instrument"}))
    cols = pd.MultiIndex.from_tuples(
        [("feature", c) for c in FEATURES] + [("label", "LABEL0")]
    )
    values = df[FEATURES + ["label"]].to_numpy(dtype=float)
    return DataHandlerLP.from_df(pd.DataFrame(values, index=idx, columns=cols))


def month_ends(dates: pd.Series) -> list[pd.Timestamp]:
    s = pd.Series(pd.to_datetime(dates).dropna().unique())
    return sorted(s.groupby(s.dt.to_period("M")).max().tolist())


def portfolio_metrics(pred: pd.Series, labels: pd.DataFrame, dates: list[pd.Timestamp],
                      one_way_bps: float = 5.0) -> dict:
    spreads, names, turns = [], [], []
    prev_long, prev_short = set(), set()
    for d in dates:
        day = pred.loc[d] if d in pred.index.get_level_values(0) else None
        if day is None:
            continue
        actual = labels[labels["Date"] == d].set_index("Ticker")["next"]
        x = pd.concat([day.rename("pred"), actual.rename("ret")], axis=1).dropna()
        if len(x) < 50:
            continue
        x["pred"] = pd.to_numeric(x["pred"], errors="coerce")
        x = x.dropna()
        if len(x) < 50:
            continue
        x["r"] = x["ret"].clip(x["ret"].quantile(.01), x["ret"].quantile(.99))
        rank = x["pred"].rank(pct=True)
        long, short = set(x[rank >= .8].index), set(x[rank <= .2].index)
        q5, q1 = x.loc[list(long), "r"].mean(), x.loc[list(short), "r"].mean()
        spreads.append(q5 - q1)
        names.append(len(x))
        turns.append((len(long - prev_long) + len(short - prev_short)) / max(len(long) + len(short), 1))
        prev_long, prev_short = long, short
    s = pd.Series(spreads, dtype=float).dropna()
    if len(s) < 3:
        return {"n_rebalances": int(len(s)), "status": "INSUFFICIENT"}
    cost = 2 * one_way_bps / 10000.0 * float(np.mean(turns))
    net = s - cost
    ann = (1 + net.mean()) ** 12 - 1
    vol = net.std(ddof=1) * np.sqrt(12)
    eq = (1 + net).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    t = net.mean() / (net.std(ddof=1) / np.sqrt(len(net))) if net.std(ddof=1) > 0 else np.nan
    return {
        "status": "OK", "n_rebalances": int(len(net)),
        "gross_mean_monthly": float(s.mean()), "net_mean_monthly": float(net.mean()),
        "ann_return": float(ann), "ann_vol": float(vol),
        "sharpe": float(ann / vol) if vol else None,
        "max_drawdown": dd, "positive_month_pct": float((net > 0).mean()),
        "t_stat": float(t), "mean_turnover": float(np.mean(turns)),
        "mean_names": float(np.mean(names)), "cost_monthly": float(cost),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", default="research_qlib_linear_baseline.json")
    args = p.parse_args(argv)
    df = prepare(args.snapshot)
    print("rows", len(df), "dates", df.Date.nunique(), "tickers", df.Ticker.nunique())
    print("range", df.Date.min().date(), df.Date.max().date())

    handler = to_handler(df)
    segments = {
        "train": ("2024-12-09", "2025-06-30"),
        "valid": ("2025-07-01", "2025-12-31"),
        "test": ("2026-01-01", "2026-10-13"),
    }
    dataset = DatasetH(handler, segments=segments)

    # Alpha selected on validation only; test is untouched.
    best = None
    for alpha in (0.1, 1.0, 10.0, 100.0):
        model = LinearModel(estimator="ridge", alpha=alpha, fit_intercept=True)
        model.fit(dataset)
        pred_valid = model.predict(dataset, segment="valid")
        valid_labels = df[df["Date"].between(segments["valid"][0], segments["valid"][1])][["Date", "Ticker", "label"]].rename(columns={"label": "next"})
        valid_dates = month_ends(valid_labels["Date"])
        metrics = portfolio_metrics(pred_valid, valid_labels, valid_dates)
        score = metrics.get("sharpe") if metrics.get("status") == "OK" else None
        print("alpha", alpha, "valid", metrics.get("status"), "sharpe", score)
        if score is not None and (best is None or score > best[0]):
            best = (score, alpha)
    alpha = best[1] if best else 1.0
    model = LinearModel(estimator="ridge", alpha=alpha, fit_intercept=True)
    model.fit(dataset)
    pred = model.predict(dataset, segment="test")
    test = df[df["Date"].between(segments["test"][0], segments["test"][1])][["Date", "Ticker", "label"]].rename(columns={"label": "next"})
    dates = month_ends(test["Date"])
    result = portfolio_metrics(pred, test, dates)

    # equal-weight benchmark on the same test dates
    bench = []
    for d in dates:
        x = test[test["Date"] == d]["next"].dropna()
        if len(x) >= 50:
            bench.append(float(x.mean()))
    b = pd.Series(bench)
    bench_stats = {
        "n_rebalances": int(len(b)),
        "ann_return": float((1 + b.mean()) ** 12 - 1) if len(b) else None,
        "ann_vol": float(b.std(ddof=1) * np.sqrt(12)) if len(b) > 1 else None,
        "sharpe": float(((1 + b.mean()) ** 12 - 1) / (b.std(ddof=1) * np.sqrt(12))) if len(b) > 1 and b.std(ddof=1) > 0 else None,
        "max_drawdown": float(((1 + b).cumprod() / (1 + b).cumprod().cummax() - 1).min()) if len(b) else None,
    }
    payload = {
        "research_only": True,
        "snapshot": args.snapshot,
        "rows": int(len(df)), "tickers": int(df.Ticker.nunique()),
        "dates": int(df.Date.nunique()),
        "features": FEATURES, "horizon": HORIZON,
        "segments": segments, "selected_alpha": alpha,
        "test": result, "equal_weight_benchmark": bench_stats,
        "qlib_version": __import__("qlib").__version__,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
