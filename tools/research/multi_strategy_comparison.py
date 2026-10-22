#!/usr/bin/env python3
"""Research-only, unified low-frequency strategy comparison; never touches production."""
from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO / "research_backtest_sp500_pit_2y.csv"
DEFAULT_SNAPSHOTS = REPO / "research_factor_snapshots_sp500_pit_2y.csv"
DEFAULT_OUTPUT = REPO / "docs" / "UNIFIED_MULTI_STRATEGY_COMPARISON.md"
HORIZON, PURGE, MIN_NAMES, TOP_FRAC = 20, 20, 30, 0.20
COSTS = (5.0, 10.0, 20.0)
FACTORS = {
    "ATR volatility": "ATR_Pct",
    "Realized volatility": "Realized_Volatility_20D_Pct",
    "Mean reversion": "ZScore_20D",
    "RSI signal": "RSI",
    "20D momentum": "Momentum_20D_Pct",
    "60D momentum": "Momentum_60D_Pct",
    "MA slope reversal": "MA20_Slope_Pct_5D",
}

def clean_frame(frame):
    required = {"Ticker", "Scan_Date", "Forward_Return_20D", *FACTORS.values()}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    d = frame[["Ticker", "Scan_Date", "Forward_Return_20D", *FACTORS.values()]].copy()
    d["Ticker"] = d["Ticker"].astype(str).str.strip().str.upper()
    d["Scan_Date"] = pd.to_datetime(d["Scan_Date"], errors="coerce").dt.normalize()
    for c in ["Forward_Return_20D", *FACTORS.values()]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=["Ticker", "Scan_Date", "Forward_Return_20D"])
    d = d[(d.Ticker != "") & (d.Forward_Return_20D > -1)]
    if d.duplicated(["Scan_Date", "Ticker"]).any():
        raise ValueError("duplicate Scan_Date/Ticker rows")
    return d.sort_values(["Scan_Date", "Ticker"]).reset_index(drop=True)

def split_dates(dates):
    dates = sorted(pd.Timestamp(x).normalize() for x in dates)
    if len(dates) < 100:
        raise ValueError(f"need at least 100 signal dates; got {len(dates)}")
    a, b = int(len(dates)*0.60), int(len(dates)*0.80)
    out = {"train": dates[:a], "validation": dates[a+PURGE:b], "test": dates[b+PURGE:]}
    if any(not x for x in out.values()):
        raise ValueError("chronological split produced an empty segment")
    return out

def daily_rows(d, dates, factor, direction):
    out = []
    for date, day in d[d.Scan_Date.isin(dates)].groupby("Scan_Date", sort=True):
        day = day.dropna(subset=[factor, "Forward_Return_20D"]).sort_values("Ticker")
        if day.Ticker.nunique() < MIN_NAMES:
            continue
        n = max(1, int(math.ceil(len(day)*TOP_FRAC)))
        ranked = day.assign(_rank=day[factor].rank(method="first"))
        chosen = ranked.nlargest(n, "_rank") if direction > 0 else ranked.nsmallest(n, "_rank")
        out.append({"date": date, "tickers": frozenset(chosen.Ticker),
                    "gross": float(chosen.Forward_Return_20D.mean()),
                    "benchmark": float(day.Forward_Return_20D.mean())})
    return out

def non_overlap(rows):
    return rows[::HORIZON]

def daily_rows_both_directions(d, dates, factor):
    """Vectorize per-date ranks, then aggregate both long-only directions."""
    wanted = set(pd.Timestamp(x).normalize() for x in dates)
    panel = d[d.Scan_Date.isin(wanted)].copy()
    # Match the reference implementation: factor-missing names are removed
    # before counting the cross-section, ranking, and computing the benchmark.
    # Counting them first can create false eligible dates and distort both
    # portfolio size and benchmark returns.
    panel = panel.dropna(subset=[factor, "Forward_Return_20D"])
    if panel.empty:
        return [], []

    groups = panel.groupby("Scan_Date", sort=True)
    counts = groups["Ticker"].transform("nunique")
    ranks = groups[factor].rank(method="first")
    picks = np.ceil(counts.to_numpy() * TOP_FRAC).astype(int)
    panel["_count"] = counts.to_numpy()
    panel["_rank"] = ranks.to_numpy()
    panel["_pick_count"] = picks
    panel = panel[panel["_count"] >= MIN_NAMES]
    if panel.empty:
        return [], []

    benchmark = panel.groupby("Scan_Date", sort=True)["Forward_Return_20D"].mean()

    def materialize(mask):
        chosen = panel.loc[mask, ["Scan_Date", "Ticker", "Forward_Return_20D"]]
        if chosen.empty:
            return []
        gross = chosen.groupby("Scan_Date", sort=True)["Forward_Return_20D"].mean()
        positions = chosen.groupby("Scan_Date", sort=True)["Ticker"].agg(frozenset)
        return [
            {
                "date": date,
                "tickers": positions.loc[date],
                "gross": float(gross.loc[date]),
                "benchmark": float(benchmark.loc[date]),
            }
            for date in gross.index
        ]

    high_mask = panel["_rank"] > (panel["_count"] - panel["_pick_count"])
    low_mask = panel["_rank"] <= panel["_pick_count"]
    return materialize(high_mask), materialize(low_mask)

def choose_direction(d, dates, factor):
    hi = non_overlap(daily_rows(d, dates, factor, 1))
    lo = non_overlap(daily_rows(d, dates, factor, -1))
    if min(len(hi), len(lo)) < 3:
        raise ValueError(f"{factor}: fewer than 3 non-overlapping training observations")
    spread = float(np.mean([x["gross"] for x in hi])-np.mean([x["gross"] for x in lo]))
    return (1 if spread >= 0 else -1), spread

def metrics(rows, cost_bps):
    if not rows:
        return {k: None for k in ("gross_pct","net_pct","benchmark_pct","excess_pct","win_pct","sharpe","drawdown_pct","turnover_pct")} | {"n": 0}
    gross, net, bench, excess, turns = [], [], [], [], []
    prev = None
    for row in rows:
        curr = row["tickers"]
        turnover = 1.0 if prev is None else 1.0-len(prev & curr)/max(1,len(prev))
        turnover = min(1.0,max(0.0,turnover))
        cost = cost_bps/10000 if prev is None else 2*turnover*cost_bps/10000
        nr = row["gross"]-cost
        gross.append(row["gross"]); net.append(nr); bench.append(row["benchmark"])
        excess.append(nr-row["benchmark"]); turns.append(turnover); prev=curr
    arr=np.asarray(net); sd=float(np.std(arr,ddof=1)) if len(arr)>1 else float("nan")
    sh=float(np.mean(arr)/sd*math.sqrt(252/HORIZON)) if len(arr)>1 and math.isfinite(sd) and sd>0 else None
    # Include initial capital as a real point in the equity curve. Slicing it
    # out before computing drawdown misses a loss in the first observation.
    wealth = np.concatenate(([1.0], np.cumprod(1 + arr)))
    peaks = np.maximum.accumulate(wealth)
    drawdowns = wealth / peaks - 1.0
    return {"n":len(rows),"gross_pct":float(np.mean(gross)*100),"net_pct":float(np.mean(net)*100),
            "benchmark_pct":float(np.mean(bench)*100),"excess_pct":float(np.mean(excess)*100),
            "win_pct":float(np.mean(arr>0)*100),"sharpe":sh,
            "drawdown_pct":float(np.min(drawdowns)*100),"turnover_pct":float(np.mean(turns)*100)}

def run_comparison(frame):
    d = clean_frame(frame)
    date_counts = d.groupby("Scan_Date").Ticker.nunique()
    dates = sorted(date_counts[date_counts >= MIN_NAMES].index.tolist())
    split_dates(dates)
    result = {}
    for label, factor in FACTORS.items():
        sub = d.dropna(subset=[factor]).copy()
        usable_dates = sorted(set(dates) & set(sub.Scan_Date.unique()))
        local = split_dates(usable_dates)

        # Group/sort each factor's date panel once. The former implementation
        # repeated this expensive grouping eight times per factor (both
        # directions, three splits, and three cost cases), which made the 10Y
        # job needlessly slow. Keep the same rows, direction rule, spacing,
        # turnover/cost calculation, and segment-specific non-overlap reset.
        high_rows, low_rows = daily_rows_both_directions(sub, usable_dates, factor)
        train_dates = set(local["train"])
        high_train = non_overlap([r for r in high_rows if r["date"] in train_dates])
        low_train = non_overlap([r for r in low_rows if r["date"] in train_dates])
        if min(len(high_train), len(low_train)) < 3:
            raise ValueError(f"{factor}: fewer than 3 non-overlapping training observations")
        train_spread = float(
            np.mean([x["gross"] for x in high_train]) -
            np.mean([x["gross"] for x in low_train])
        )
        direction = 1 if train_spread >= 0 else -1
        chosen_rows = high_rows if direction > 0 else low_rows

        segments = {}
        for name, ds in local.items():
            date_set = set(ds)
            segment_rows = [r for r in chosen_rows if r["date"] in date_set]
            segments[name] = metrics(non_overlap(segment_rows), 10.0)

        test_dates = set(local["test"])
        test_rows = non_overlap([r for r in chosen_rows if r["date"] in test_dates])
        costs = {str(int(c)): metrics(test_rows, c) for c in COSTS}
        result[label] = {
            "factor": factor,
            "direction": "HIGH" if direction > 0 else "LOW",
            "train_spread_pct": train_spread * 100,
            "segments": segments,
            "costs": costs,
            "dates": len(usable_dates),
            "tickers": int(sub.Ticker.nunique()),
        }
    return {
        "rows": len(d),
        "tickers": int(d.Ticker.nunique()),
        "dates": len(dates),
        "start": dates[0].strftime("%Y-%m-%d"),
        "end": dates[-1].strftime("%Y-%m-%d"),
        "results": result,
    }

def render_report(r):
    lines=["# Unified low-frequency strategy comparison (research only)","",
      "> Research-only; no production changes. Signal directions are selected on training data and frozen for validation/test.",
      "> This is not a blind test: the source panel has been used in exploratory analysis. PIT membership and corporate-action limitations remain.",
      "",f"- Data: {r['rows']:,} rows, {r['tickers']} tickers, {r['dates']} valid signal dates ({r['start']} to {r['end']}).",
      "- Portfolio: top/bottom 20% equal-weight long-only; 20-session non-overlapping observations; 20-date purge at split boundaries.",
      "- Costs: turnover-based estimate at 5/10/20 bps per side; not a fill-level slippage model.","",
      "## Test-set comparison (10 bps per side)","","| Strategy | Factor | Frozen direction | n | Gross %/20D | Net %/20D | Net excess %/20D | Win % | Sharpe* | Drawdown % | Turnover % |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label,x in r["results"].items():
        m=x["segments"]["test"]
        def f(k):
            return "NA" if m[k] is None else f"{m[k]:+.3f}"
        sh="NA" if m["sharpe"] is None else f"{m['sharpe']:.2f}"
        lines.append(f"| {label} | {x['factor']} | {x['direction']} | {m['n']} | {f('gross_pct')} | {f('net_pct')} | {f('excess_pct')} | {f('win_pct')} | {sh} | {f('drawdown_pct')} | {f('turnover_pct')} |")
    lines += ["","*Sharpe is a rough annualization of non-overlapping 20-day returns. Small test counts mean weak evidence.","",
      "## Test cost sensitivity (net % per 20 sessions)","","| Strategy | 5 bps/side | 10 bps/side | 20 bps/side |","|---|---:|---:|---:|"]
    for label,x in r["results"].items():
        vals=[x["costs"][str(int(c))]["net_pct"] for c in COSTS]
        lines.append("| "+label+" | "+" | ".join("NA" if v is None else f"{v:+.3f}%" for v in vals)+" |")
    lines += ["","## Split details","","| Strategy | Split | n | Net %/20D | Net excess %/20D | Win % | Sharpe |","|---|---|---:|---:|---:|---:|---:|"]
    for label,x in r["results"].items():
        for split,m in x["segments"].items():
            net="NA" if m["net_pct"] is None else f"{m['net_pct']:+.3f}"
            ex="NA" if m["excess_pct"] is None else f"{m['excess_pct']:+.3f}"
            win="NA" if m["win_pct"] is None else f"{m['win_pct']:.1f}"
            sh="NA" if m["sharpe"] is None else f"{m['sharpe']:.2f}"
            lines.append(f"| {label} | {split} | {m['n']} | {net} | {ex} | {win} | {sh} |")
    lines += ["","## Interpretation guardrails","",
      "- Do not pick a winner after looking at the test results or reverse a direction using test data.",
      "- Positive historical net excess is not proof of live alpha; production gates, stop execution, liquidity, slippage, and fill failures are not fully simulated.",
      "- Treat any strategy with fewer than 8 test observations as insufficient evidence. Evaluating more candidate factors increases multiple-comparison/data-mining risk; do not infer a winner from this exploratory panel.",
      "- This script does not change production scoring, scan, stops, portfolio, or ledger.",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=DEFAULT_INPUT,help="backtest returns CSV")
    p.add_argument("--snapshots",type=Path,default=DEFAULT_SNAPSHOTS,help="factor snapshot CSV")
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    a=p.parse_args()
    for path in (a.input, a.snapshots):
        if not path.exists(): raise SystemExit(f"missing input: {path}")
    # Factors and forward returns live in separate panels; join on the PIT
    # ticker/date key used by the existing research pipeline.
    snap=pd.read_csv(a.snapshots,dtype=str,keep_default_na=False)
    bt=pd.read_csv(a.input,dtype=str,keep_default_na=False,
                   usecols=["Ticker","Technical_Date","Forward_Return_20D"])
    key=["Ticker","Technical_Date"]
    missing=[col for col in key + list(FACTORS.values()) if col not in snap.columns]
    if missing: raise SystemExit(f"snapshot file missing required columns: {missing}")
    frame=snap[key + list(FACTORS.values())].merge(bt,on=key,how="inner",validate="one_to_one")
    frame=frame.rename(columns={"Technical_Date":"Scan_Date"})
    result=run_comparison(frame)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(render_report(result),encoding="utf-8")
    print(f"wrote {a.output}; rows={result['rows']} dates={result['dates']} strategies={len(result['results'])}")
    for label,x in result["results"].items():
        m=x["segments"]["test"]
        print(f"{label}: direction={x['direction']} n={m['n']} net={m['net_pct']} excess={m['excess_pct']}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
