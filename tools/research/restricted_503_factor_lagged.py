#!/usr/bin/env python3
"""Fixed five-factor validation on the restricted 466-ticker current universe.

CURRENT-UNIVERSE EXPLORATORY — SURVIVORSHIP-BIASED
NOT A FULL PIT RESULT
NOT DEPLOYABLE ALPHA

This is not a parameter search: five directions, one horizon, one rebalance
frequency, one cost model.  The train/test split is chronological and no
parameter is selected from the test period.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HORIZON = 20
REBALANCE = 20
COST_BPS = 5.0
WINSOR = (0.01, 0.99)
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 5_000_000.0
FACTORS = {
    "Vol60": (-1, "low realized volatility"),
    "ATR_Pct": (-1, "low average true range"),
    "Mom12_1": (1, "12-1 momentum"),
    "Mom1": (-1, "one-month reversal"),
    "MA50": (1, "price above 50-day average"),
}
LABEL = "LAGGED EXECUTION SENSITIVITY — NEXT OPEN ENTRY — SURVIVORSHIP-BIASED | NOT PIT | NOT DEPLOYABLE"


def load_panel(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    required = {"Date", "Ticker", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"missing columns: {sorted(missing)}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    for c in ("High", "Low", "Close", "Volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Date", "Ticker", "Close"]).sort_values(["Ticker", "Date"])
    dates = df["Date"].dropna().unique()
    complete = df.groupby("Ticker")["Date"].nunique()
    complete = set(complete[complete == len(dates)].index)
    df = df[df["Ticker"].isin(complete)].copy()
    g = df.groupby("Ticker", group_keys=False)
    df["ret"] = g["Close"].pct_change()
    df["Vol60"] = g["ret"].apply(lambda s: s.rolling(60).std() * np.sqrt(252))
    prev = g["Close"].shift(1)
    tr = pd.concat([(df["High"] - df["Low"]),
                    (df["High"] - prev).abs(),
                    (df["Low"] - prev).abs()], axis=1).max(axis=1)
    df["ATR14"] = tr.groupby(df["Ticker"]).transform(lambda s: s.rolling(14).mean())
    df["ATR_Pct"] = df["ATR14"] / df["Close"]
    df["Mom12_1"] = g["Close"].apply(lambda s: s.shift(21) / s.shift(252) - 1)
    df["Mom1"] = g["Close"].apply(lambda s: s / s.shift(21) - 1)
    df["MA50"] = g["Close"].apply(lambda s: s / s.rolling(50).mean() - 1)
    df["DV20"] = (df["Close"] * df["Volume"]).groupby(df["Ticker"]).transform(lambda s: s.rolling(20).mean())
    entry_open = g["Open"].shift(-1)
    exit_open = g["Open"].shift(-(1 + HORIZON))
    df["Fwd20"] = exit_open / entry_open - 1
    return df


def month_ends(df: pd.DataFrame) -> list[pd.Timestamp]:
    s = pd.Series(pd.to_datetime(df["Date"]).dropna().unique())
    return sorted(s.groupby(s.dt.to_period("M")).max().tolist())


def evaluate(df: pd.DataFrame, name: str, direction: int, dates: list[pd.Timestamp],
             cost_bps: float = COST_BPS) -> dict:
    prev_long, prev_short = set(), set()
    rows = []
    for d in dates:
        x = df[(df["Date"] == d) & (df["Close"] >= MIN_PRICE) & (df["DV20"] >= MIN_DOLLAR_VOLUME)]
        x = x[["Ticker", name, "Fwd20"]].dropna()
        if len(x) < 80:
            continue
        lo, hi = x["Fwd20"].quantile(list(WINSOR))
        x["r"] = x["Fwd20"].clip(lo, hi)
        rank = x[name].rank(pct=True)
        long, short = set(x[rank >= .8]["Ticker"]), set(x[rank <= .2]["Ticker"])
        q5, q1 = x[x["Ticker"].isin(long)]["r"].mean(), x[x["Ticker"].isin(short)]["r"].mean()
        turnover = 1.0 if not (prev_long or prev_short) else (
            len(long - prev_long) + len(short - prev_short)
        ) / max(len(long) + len(short), 1)
        gross = direction * (q5 - q1)
        rows.append({"date": d.isoformat(), "gross": gross, "turnover": turnover,
                     "cost": cost_bps / 10000.0 * turnover,
                     "net": gross - cost_bps / 10000.0 * turnover,
                     "n": len(x), "n_long": len(long), "n_short": len(short)})
        prev_long, prev_short = long, short
    return {"rows": rows}


def metrics(rows: list[dict], label: str) -> dict:
    if len(rows) < 3:
        return {"sample": label, "n": len(rows), "status": "INSUFFICIENT"}
    s = pd.DataFrame(rows)
    net = s["net"].to_numpy()
    ann = float(np.prod(1 + net) ** (12 / len(net)) - 1)
    vol = float(np.std(net, ddof=1) * np.sqrt(12))
    eq = np.cumprod(1 + net)
    t = float(net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))) if net.std(ddof=1) > 0 else None
    return {
        "sample": label, "n": len(net), "gross_mean": float(s["gross"].mean()),
        "net_mean": float(net.mean()), "ann_return": ann, "ann_vol": vol,
        "sharpe": float(ann / vol) if vol else None,
        "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()),
        "positive_pct": float((net > 0).mean()), "t_stat": t,
        "p_value": float(2 * stats.t.sf(abs(t), len(net) - 1)) if t is not None else None,
        "mean_turnover": float(s["turnover"].mean()), "mean_names": float(s["n"].mean()),
        "mean_long": float(s["n_long"].mean()), "mean_short": float(s["n_short"].mean()),
    }


def bh(pvalues: list[float]) -> list[float]:
    p = np.asarray(pvalues, float)
    n = len(p)
    order = np.argsort(p)
    raw = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(raw[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out.tolist()


def benchmark(df: pd.DataFrame, dates: list[pd.Timestamp]) -> dict:
    rows = []
    for d in dates:
        x = df[(df["Date"] == d) & (df["Close"] >= MIN_PRICE) & (df["DV20"] >= MIN_DOLLAR_VOLUME)]
        x = x[["Fwd20"]].dropna()
        if len(x) >= 80:
            r = float(x["Fwd20"].mean())
            rows.append({"gross": r, "turnover": 0.0, "cost": 0.0, "net": r,
                         "n": len(x), "n_long": 0, "n_short": 0})
    return metrics(rows, "equal_weight_benchmark")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-panel", required=True)
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args(argv)
    df = load_panel(args.price_panel)
    dates = month_ends(df)
    full = []
    for name, (direction, rationale) in FACTORS.items():
        rows = evaluate(df, name, direction, dates)["rows"]
        for label, subset in (
            ("all", rows),
            ("train_2016_2022", [r for r in rows if r["date"] < "2023-01-01"]),
            ("test_2023_2026", [r for r in rows if r["date"] >= "2023-01-01"]),
        ):
            m = metrics(subset, label)
            m.update({"factor": name, "direction": direction, "rationale": rationale,
                      "label": LABEL})
            full.append(m)
    out = pd.DataFrame(full)
    valid = out[(out["sample"] == "test_2023_2026") & out["p_value"].notna()]
    qmap = dict(zip(valid["factor"], bh(valid["p_value"].tolist())))
    out["bh_q_test"] = out["factor"].map(qmap)
    prefix = Path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(prefix.with_suffix(".csv"), index=False, encoding="utf-8")
    payload = {
        "label": LABEL,
        "rows": int(len(df)),
        "tickers": int(df["Ticker"].nunique()),
        "dates": int(df["Date"].nunique()),
        "date_min": str(df["Date"].min().date()),
        "date_max": str(df["Date"].max().date()),
        "horizon": HORIZON, "rebalance_sessions": REBALANCE,
        "cost_bps": COST_BPS, "winsor": WINSOR,
        "factors": {k: {"direction": v[0], "rationale": v[1]} for k, v in FACTORS.items()},
        "benchmark": benchmark(df, dates),
        "results": out.to_dict(orient="records"),
    }
    prefix.with_suffix(".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
