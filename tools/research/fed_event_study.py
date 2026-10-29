#!/usr/bin/env python3
"""Minimal Fed-event / SPY feasibility study.

Uses exact Fed press-release timestamps and SPY daily opens/closes. This is a
retrospective, counterfactual event study: it does not claim PIT availability.
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
    p.add_argument("--spy", required=True)
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--cost-bps", type=float, default=5.0)
    args = p.parse_args(argv)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))["rows"]
    spy = pd.read_csv(args.spy)
    spy["Date"] = pd.to_datetime(spy["Date"])
    spy = spy.dropna(subset=["Date", "Open", "Close"]).sort_values("Date").set_index("Date")
    sessions = list(spy.index)
    cal = xcals.get_calendar("XNYS")
    schedule = cal.schedule
    rows = []
    for e in events:
        ts = pd.Timestamp(e["published_at_utc"])
        # First session whose open is at/after event time, unless event is
        # before that session's open, in which case use the same open.
        candidates = [s for s in sessions if s.date() >= ts.date()]
        if not candidates:
            continue
        entry = None
        for s in candidates:
            op = schedule.loc[s, "open"].tz_convert("UTC") if schedule.loc[s, "open"].tz else schedule.loc[s, "open"]
            if ts < op:
                entry = s
                break
            if ts.date() == s.date():
                # event after open: next session
                continue
        if entry is None:
            continue
        idx = sessions.index(entry)
        if idx + 5 >= len(sessions):
            continue
        entry_open = float(spy.loc[entry, "Open"])
        close1 = float(spy.iloc[idx + 1]["Close"])
        close5 = float(spy.iloc[idx + 5]["Close"])
        gross1 = close1 / entry_open - 1
        gross5 = close5 / entry_open - 1
        net1 = gross1 - args.cost_bps / 10000 * 2
        net5 = gross5 - args.cost_bps / 10000 * 2
        rows.append({"event_id": e.get("source_event_id"), "published_at_utc": e["published_at_utc"],
                     "entry_date": entry.date().isoformat(), "entry_open": entry_open,
                     "plus1_date": sessions[idx + 1].date().isoformat(), "plus5_date": sessions[idx + 5].date().isoformat(),
                     "gross_1d": gross1, "net_1d": net1, "gross_5d": gross5, "net_5d": net5})
    df = pd.DataFrame(rows)
    # One observation per entry date: first event, to avoid same-day duplicates.
    unique = df.drop_duplicates("entry_date", keep="first").copy()
    # Same-window unconditional SPY baseline over the event period.
    start = pd.Timestamp(df["entry_date"].min())
    end = pd.Timestamp(df["entry_date"].max())
    base_rows = []
    for i, s in enumerate(sessions):
        if s < start or s > end or i + 5 >= len(sessions):
            continue
        base_rows.append({"gross_1d": float(spy.iloc[i + 1]["Close"]) / float(spy.iloc[i]["Open"]) - 1,
                          "gross_5d": float(spy.iloc[i + 5]["Close"]) / float(spy.iloc[i]["Open"]) - 1})
    base = pd.DataFrame(base_rows)
    def summary(x):
        return {"n": int(len(x)),
                "mean_gross_1d": float(x["gross_1d"].mean()) if len(x) else None,
                "mean_net_1d": float(x["net_1d"].mean()) if "net_1d" in x and len(x) else None,
                "mean_gross_5d": float(x["gross_5d"].mean()) if len(x) else None,
                "mean_net_5d": float(x["net_5d"].mean()) if "net_5d" in x and len(x) else None}
    payload = {
        "events_total": len(events), "events_with_windows": len(df),
        "unique_entry_dates": len(unique), "cost_bps_one_way": args.cost_bps,
        "entry_rule": "event before open -> same open; at/after open -> next session open",
        "horizon": "entry open -> close of entry+1 / entry+5 sessions",
        "sample": summary(unique), "unconditional_spy": summary(base),
        "observation_mode": "retrospective_counterfactual_not_pit",
        "note": "SPY is a market proxy; no PIT first-seen evidence; overlapping event windows.",
    }
    Path(args.output_prefix + ".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    df.to_csv(args.output_prefix + "_events.csv", index=False)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
