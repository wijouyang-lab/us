#!/usr/bin/env python3
"""FOMC statement event study on multiple ETF proxies.

Exact release time from Fed pages; next-session open entry for 2 p.m. ET
statements. Retrospective, not PIT. Raw OHLC, no dividend adjustment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import exchange_calendars as xcals


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--proxy-dir", required=True)
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--cost-bps", type=float, default=5.0)
    args = p.parse_args(argv)
    raw = json.loads(Path(args.events).read_text(encoding="utf-8"))["events"]
    events = [e for e in raw if e.get("parse_status") == "exact"
              and "Longer-Run Goals" not in (e.get("title") or "")]
    cal = xcals.get_calendar("XNYS")
    schedule = cal.schedule
    results = []
    detail = []
    for proxy in ["SPY", "QQQ", "IWM", "TLT", "GLD"]:
        px = pd.read_csv(Path(args.proxy_dir) / f"{proxy}.csv")
        px["Date"] = pd.to_datetime(px["Date"])
        px = px.dropna(subset=["Date", "Open", "Close"]).sort_values("Date").set_index("Date")
        sessions = list(px.index)
        rows = []
        for e in events:
            ts = pd.Timestamp(e["published_at_utc"])
            entry = None
            for s in [x for x in sessions if x.date() >= ts.date()]:
                op = schedule.loc[s, "open"]
                op = op.tz_convert("UTC") if getattr(op, "tz", None) else op
                if ts < op:
                    entry = s
                    break
            if entry is None:
                continue
            i = sessions.index(entry)
            if i + 5 >= len(sessions):
                continue
            gross1 = float(px.iloc[i + 1]["Close"]) / float(px.loc[entry, "Open"]) - 1
            gross5 = float(px.iloc[i + 5]["Close"]) / float(px.loc[entry, "Open"]) - 1
            cost = args.cost_bps / 10000 * 2
            rows.append({"proxy": proxy, "event_id": e["event_id"],
                         "published_at_utc": e["published_at_utc"],
                         "entry_date": entry.date().isoformat(),
                         "plus1_date": sessions[i + 1].date().isoformat(),
                         "plus5_date": sessions[i + 5].date().isoformat(),
                         "gross_1d": gross1, "net_1d": gross1 - cost,
                         "gross_5d": gross5, "net_5d": gross5 - cost})
            detail.append(rows[-1])
        if rows:
            x = pd.DataFrame(rows)
            start, end = pd.Timestamp(x.entry_date.min()), pd.Timestamp(x.entry_date.max())
            base = []
            for i, s in enumerate(sessions):
                if s < start or s > end or i + 5 >= len(sessions):
                    continue
                base.append({"gross_1d": float(px.iloc[i + 1]["Close"]) / float(px.iloc[i]["Open"]) - 1,
                             "gross_5d": float(px.iloc[i + 5]["Close"]) / float(px.iloc[i]["Open"]) - 1})
            b = pd.DataFrame(base)
            results.append({"proxy": proxy, "n": len(x), "unique_entry_dates": x.entry_date.nunique(),
                            "mean_gross_1d": float(x.gross_1d.mean()), "mean_net_1d": float(x.net_1d.mean()),
                            "mean_gross_5d": float(x.gross_5d.mean()), "mean_net_5d": float(x.net_5d.mean()),
                            "baseline_n": len(b), "baseline_gross_1d": float(b.gross_1d.mean()),
                            "baseline_gross_5d": float(b.gross_5d.mean())})
    out = pd.DataFrame(detail)
    out.to_csv(args.output_prefix + "_events.csv", index=False)
    payload = {"event_type": "FOMC_statement", "events_source": args.events,
               "events_total": len(raw), "events_used": len(events),
               "cost_bps_one_way": args.cost_bps, "round_trip_cost_bps": args.cost_bps * 2,
               "entry_rule": "event before open -> same open; at/after open -> next session open",
               "price": "raw open/close; no dividend/split adjustment for short window",
               "observation_mode": "retrospective_counterfactual_not_pit",
               "proxies": results}
    Path(args.output_prefix + ".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
