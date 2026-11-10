#!/usr/bin/env python3
"""Audit historical S&P 500 membership against the existing price panel.

External membership snapshots are community-compiled candidates, not official
truth. This script does not download prices and does not write the panel.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def norm(t: str) -> str:
    return str(t).strip().upper().replace(".", "-")


def load_snapshots(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    rows = []
    for _, r in df.iterrows():
        for t in str(r["tickers"]).split(","):
            if t.strip():
                rows.append({"date": r["date"], "ticker": norm(t)})
    return pd.DataFrame(rows).drop_duplicates()


def snapshot_on(exp: pd.DataFrame, d: pd.Timestamp) -> set[str]:
    x = exp[exp["date"] <= d]
    if x.empty:
        return set()
    last = x["date"].max()
    return set(x[x["date"] == last]["ticker"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chino", required=True)
    p.add_argument("--thun", required=True)
    p.add_argument("--panel", required=True)
    p.add_argument("--output-prefix", required=True)
    args = p.parse_args(argv)

    chino = load_snapshots(args.chino)
    thun = load_snapshots(args.thun)
    panel = pd.read_csv(args.panel, usecols=["Date", "Ticker"])
    panel["Date"] = pd.to_datetime(panel["Date"], errors="coerce")
    panel["ticker"] = panel["Ticker"].map(norm)
    panel_first = panel.groupby("ticker")["Date"].min().to_dict()
    panel_last = panel.groupby("ticker")["Date"].max().to_dict()
    panel_set = set(panel["ticker"].unique())

    years = list(range(2016, 2027))
    year_rows = []
    detail = []
    for y in years:
        d = pd.Timestamp(f"{y}-12-31")
        c = snapshot_on(chino, d)
        t = snapshot_on(thun, d)
        for ticker in sorted(c):
            first = panel_first.get(ticker)
            status = "missing" if ticker not in panel_set else (
                "has_price_late" if first is not None and first > d else "has_price")
            detail.append({"year": y, "ticker": ticker, "in_panel": ticker in panel_set,
                           "panel_first": first.date().isoformat() if first is not None else None,
                           "panel_last": panel_last[ticker].date().isoformat() if ticker in panel_set else None,
                           "snapshot_date": d.date().isoformat(),
                           "status": status})
        year_rows.append({"year": y, "chino_count": len(c), "thun_count": len(t),
                          "common_count": len(c & t), "chino_only": len(c - t),
                          "thun_only": len(t - c),
                          "in_panel": sum(1 for x in c if x in panel_set),
                          "missing": sum(1 for x in c if x not in panel_set)})

    detail = pd.DataFrame(detail)
    summary = pd.DataFrame(year_rows)
    missing = detail[detail["status"] == "missing"]
    detail.to_csv(args.output_prefix + "_detail.csv", index=False)
    summary.to_csv(args.output_prefix + "_yearly.csv", index=False)
    missing.to_csv(args.output_prefix + "_missing.csv", index=False)

    common_dates = sorted(set(chino["date"]).intersection(set(thun["date"])))
    jac = []
    for d in common_dates:
        c = snapshot_on(chino, d)
        t = snapshot_on(thun, d)
        if c or t:
            jac.append({"date": d.date().isoformat(), "jaccard": len(c & t) / len(c | t),
                        "chino_only": len(c - t), "thun_only": len(t - c)})
    jac_df = pd.DataFrame(jac)
    payload = {
        "sources": {
            "chino": {"url": "https://github.com/chinobing/historical_sp500_constituents",
                      "license": "MIT", "rows": int(pd.read_csv(args.chino).shape[0]),
                      "date_min": str(chino.date.min().date()), "date_max": str(chino.date.max().date())},
            "thun": {"url": "https://github.com/thuningxu/sp500nq100",
                     "license": "no repository license found", "rows": int(pd.read_csv(args.thun).shape[0]),
                     "date_min": str(thun.date.min().date()), "date_max": str(thun.date.max().date())},
            "panel": {"path": args.panel, "tickers": len(panel_set),
                      "date_min": str(panel.Date.min().date()), "date_max": str(panel.Date.max().date())},
        },
        "common_snapshot_dates": len(common_dates),
        "jaccard_min": float(jac_df.jaccard.min()) if len(jac_df) else None,
        "jaccard_mean": float(jac_df.jaccard.mean()) if len(jac_df) else None,
        "jaccard_below_0_98": int((jac_df.jaccard < 0.98).sum()) if len(jac_df) else None,
        "yearly": year_rows,
        "missing_rows": int(len(missing)),
    }
    Path(args.output_prefix + "_source_comparison.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("common_snapshot_dates", "jaccard_min", "jaccard_mean",
                                             "jaccard_below_0_98", "missing_rows")}, indent=2))
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
