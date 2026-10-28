#!/usr/bin/env python3
"""Independent audit of the Qlib low-frequency long/short backtest.

Recomputes the return series and portfolio metrics from frozen model
predictions, with:
  - training-only winsor thresholds (no test-distribution fitting),
  - explicit one-way turnover and cost definition,
  - compounded annualization,
  - bootstrap confidence intervals,
  - equal-weight benchmark and market-adjusted alpha on the same dates.

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

from qlib_lowfreq_baseline import FEATURES, month_ends, prepare, to_handler

HORIZON = 20
ALPHA = 0.1
SEGMENTS = {
    "train": ("2024-12-09", "2025-06-30"),
    "valid": ("2025-07-01", "2025-12-31"),
    "test": ("2026-01-01", "2026-10-13"),
}


def monthly_records(pred: pd.Series, labels: pd.DataFrame, dates: list[pd.Timestamp],
                    winsor: tuple[float, float]) -> list[dict]:
    recs = []
    prev_long, prev_short = set(), set()
    for d in dates:
        if d not in pred.index.get_level_values(0):
            continue
        actual = labels[labels["Date"] == d].set_index("Ticker")["next"]
        x = pd.concat([pred.loc[d].rename("pred"), actual.rename("ret")], axis=1).dropna()
        if len(x) < 50:
            continue
        x["pred"] = pd.to_numeric(x["pred"], errors="coerce")
        x = x.dropna()
        if len(x) < 50:
            continue
        x["r"] = x["ret"].clip(winsor[0], winsor[1])
        rank = x["pred"].rank(pct=True)
        long, short = set(x[rank >= .8].index), set(x[rank <= .2].index)
        q5, q1 = x.loc[list(long), "r"].mean(), x.loc[list(short), "r"].mean()
        # One-way traded fraction of gross notional. Initial book = 1.0.
        if prev_long or prev_short:
            turnover = (len(long - prev_long) + len(short - prev_short)) / max(len(long) + len(short), 1)
        else:
            turnover = 1.0
        recs.append({
            "date": d.strftime("%Y-%m-%d"),
            "q5": float(q5), "q1": float(q1), "gross": float(q5 - q1),
            "turnover": float(turnover),
            "n_all": int(len(x)), "n_long": len(long), "n_short": len(short),
            "long": sorted(long), "short": sorted(short),
        })
        prev_long, prev_short = long, short
    return recs


def metrics(records: list[dict], one_way_bps: float) -> dict:
    if len(records) < 3:
        return {"status": "INSUFFICIENT", "n": len(records)}
    gross = np.array([r["gross"] for r in records])
    turnover = np.array([r["turnover"] for r in records])
    # One-way cost applies to the one-way traded fraction; turnover is already
    # measured as one-way name changes relative to the gross book.
    cost = one_way_bps / 10000.0 * turnover
    net = gross - cost
    n = len(net)
    ann = float(np.prod(1 + net) ** (12 / n) - 1)
    vol = float(np.std(net, ddof=1) * np.sqrt(12))
    sharpe = ann / vol if vol else None
    eq = np.cumprod(1 + net)
    dd = float(np.min(eq / np.maximum.accumulate(eq) - 1))
    t = float(np.mean(net) / (np.std(net, ddof=1) / np.sqrt(n))) if np.std(net, ddof=1) > 0 else None
    return {
        "status": "OK", "n_rebalances": n,
        "gross_mean_monthly": float(gross.mean()),
        "net_mean_monthly": float(net.mean()),
        "ann_return": ann, "ann_vol": vol, "sharpe": sharpe,
        "max_drawdown": dd, "positive_month_pct": float((net > 0).mean()),
        "t_stat": t,
        "mean_turnover": float(turnover.mean()),
        "mean_cost_monthly": float(cost.mean()),
        "avg_all_names": float(np.mean([r["n_all"] for r in records])),
        "avg_long_names": float(np.mean([r["n_long"] for r in records])),
        "avg_short_names": float(np.mean([r["n_short"] for r in records])),
    }


def market_adjusted(records: list[dict], ew: pd.Series, value: str = "gross") -> dict:
    z = pd.DataFrame(records).set_index("date")
    z.index = pd.to_datetime(z.index)
    z = z[[value]].join(ew.rename("ew"), how="inner").dropna()
    if len(z) < 4:
        return {"status": "INSUFFICIENT", "n": len(z), "value": value}
    y = z[value].to_numpy()
    X = np.column_stack([np.ones(len(z)), z["ew"].to_numpy()])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ coef
    sigma2 = np.sum(resid ** 2) / (len(z) - 2)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se_alpha = float(np.sqrt(cov[0, 0]))
    return {
        "status": "OK", "n": len(z), "value": value, "alpha_monthly": float(coef[0]),
        "beta": float(coef[1]), "alpha_t": float(coef[0] / se_alpha) if se_alpha else None,
        "alpha_ci95": [float(coef[0] - 1.96 * se_alpha), float(coef[0] + 1.96 * se_alpha)],
    }


def bootstrap_ci(net: np.ndarray, n_boot: int = 5000, seed: int = 7) -> dict:
    if len(net) < 3:
        return {}
    rng = np.random.default_rng(seed)
    means = []
    sharpes = []
    for _ in range(n_boot):
        s = rng.choice(net, len(net), replace=True)
        means.append(s.mean())
        sd = s.std(ddof=1)
        sharpes.append(s.mean() / sd * np.sqrt(12) if sd > 0 else np.nan)
    return {
        "mean_ci95": [float(np.nanpercentile(means, 2.5)), float(np.nanpercentile(means, 97.5))],
        "sharpe_ci95": [float(np.nanpercentile(sharpes, 2.5)), float(np.nanpercentile(sharpes, 97.5))],
    }


def walk_forward_records(df: pd.DataFrame, handler, test_dates: list[pd.Timestamp],
                         one_way_bps: float = 5.0) -> list[dict]:
    """Refit on an expanding window, purging one full 20-session label window.

    Every test date only uses rows whose labels were complete by the prior
    session. Winsor thresholds are recomputed from that window's training
    labels, not from the test dates.
    """
    sessions = sorted(pd.to_datetime(df["Date"]).dropna().unique())
    prev_long, prev_short = set(), set()
    out = []
    for d in test_dates:
        prior = [s for s in sessions if s < d]
        if len(prior) < 80:
            continue
        train_end = prior[-21]  # 20-session label + 1-session embargo
        train = df[(df["Date"] <= train_end) & df["label"].notna()]
        if len(train) < 500:
            continue
        winsor = (float(train["label"].quantile(.01)), float(train["label"].quantile(.99)))
        ds = DatasetH(handler, segments={
            "train": (str(sessions[0].date()), str(pd.Timestamp(train_end).date())),
            "test": (str(d.date()), str(d.date())),
        })
        model = LinearModel(estimator="ridge", alpha=ALPHA, fit_intercept=True).fit(ds)
        pred = model.predict(ds, segment="test")
        actual = df[df["Date"] == d][["Ticker", "label"]].rename(columns={"label": "next"}).set_index("Ticker")["next"]
        day = pred.loc[d] if d in pred.index.get_level_values(0) else pd.Series(dtype=float)
        x = pd.concat([day.rename("pred"), actual.rename("ret")], axis=1).dropna()
        if len(x) < 50:
            continue
        x["r"] = x["ret"].clip(winsor[0], winsor[1])
        rank = x["pred"].rank(pct=True)
        long, short = set(x[rank >= .8].index), set(x[rank <= .2].index)
        q5, q1 = x.loc[list(long), "r"].mean(), x.loc[list(short), "r"].mean()
        turnover = 1.0 if not (prev_long or prev_short) else (
            len(long - prev_long) + len(short - prev_short)
        ) / max(len(long) + len(short), 1)
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "train_start": str(min(train["Date"]).date()),
            "train_end": str(pd.Timestamp(train_end).date()),
            "train_rows": int(len(train)),
            "feature_count": len(FEATURES),
            "alpha": ALPHA,
            "n_all": int(len(x)),
            "n_missing": int(len(actual) - len(x)),
            "n_long": len(long), "n_short": len(short),
            "gross": float(q5 - q1), "cost": float(one_way_bps / 10000 * turnover),
            "net": float(q5 - q1 - one_way_bps / 10000 * turnover),
            "turnover": float(turnover),
            "long": sorted(long), "short": sorted(short),
        })
        prev_long, prev_short = long, short
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", default="research_qlib_backtest_audit.json")
    args = p.parse_args(argv)
    df = prepare(args.snapshot)
    handler = to_handler(df)
    ds = DatasetH(handler, segments=SEGMENTS)
    model = LinearModel(estimator="ridge", alpha=ALPHA, fit_intercept=True).fit(ds)
    pred = model.predict(ds, segment="test")
    test = df[df["Date"].between(*SEGMENTS["test"])][["Date", "Ticker", "label"]].rename(columns={"label": "next"})
    dates = month_ends(test["Date"])
    # Winsor thresholds are learned from TRAIN labels only, not test.
    train_labels = df[df["Date"].between(*SEGMENTS["train"])]["label"]
    winsor = (float(train_labels.quantile(.01)), float(train_labels.quantile(.99)))

    records = monthly_records(pred, test, dates, winsor)
    wf_records = walk_forward_records(df, handler, dates)
    ew = []
    for d in dates:
        x = test[test["Date"] == d]["next"].dropna()
        if len(x) >= 50:
            ew.append({"date": d, "ew": float(x.mean())})
    ew_s = pd.DataFrame(ew).set_index("date")["ew"]
    net_arr = np.array([r["gross"] for r in records]) - 5 / 10000.0 * np.array([r["turnover"] for r in records])
    net_records = [
        {**r, "net": r["gross"] - 5 / 10000.0 * r["turnover"]}
        for r in records
    ]
    half = len(records) // 2
    payload = {
        "research_only": True,
        "snapshot": args.snapshot,
        "winsor_thresholds_from_train": winsor,
        "model": {"type": "qlib.LinearModel", "estimator": "ridge", "alpha": ALPHA},
        "segments": SEGMENTS,
        "test_dates": [r["date"] for r in records],
        "test": metrics(records, 5.0),
        "test_10bps": metrics(records, 10.0),
        "test_20bps": metrics(records, 20.0),
        "walk_forward_5bps": metrics(wf_records, 5.0) if wf_records else {"status": "INSUFFICIENT"},
        "walk_forward_windows": wf_records,
        "test_first_half": metrics(records[:half], 5.0) if half >= 3 else {"status": "INSUFFICIENT"},
        "test_second_half": metrics(records[half:], 5.0) if len(records) - half >= 3 else {"status": "INSUFFICIENT"},
        "benchmark": {
            "mean_monthly": float(ew_s.mean()) if len(ew_s) else None,
            "ann_return": float((1 + ew_s.mean()) ** 12 - 1) if len(ew_s) else None,
            "sharpe": float(((1 + ew_s.mean()) ** 12 - 1) / (ew_s.std(ddof=1) * np.sqrt(12))) if len(ew_s) > 1 and ew_s.std(ddof=1) > 0 else None,
        },
        "market_adjusted_gross": market_adjusted(records, ew_s, "gross"),
        "market_adjusted_net": market_adjusted(net_records, ew_s, "net"),
        "bootstrap_test_5bps": bootstrap_ci(net_arr),
        "monthly": records,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("winsor_thresholds_from_train", "test", "test_10bps", "test_20bps", "test_first_half", "test_second_half", "benchmark", "market_adjusted_gross", "market_adjusted_net", "bootstrap_test_5bps")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
