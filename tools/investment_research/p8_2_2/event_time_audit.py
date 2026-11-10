"""P8.2.2 event timestamp provenance.

Today's VERIFIED_* classes are post-hoc. The formal signal uses a deterministic
price rule with an event-date availability timestamp. This module records the
distinction and provides a time-travel-safe helper for tests.
"""
from __future__ import annotations
import csv,json
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p8_2_2";THRESH=5.0


def available_on(event_date: date, decision_date: date, detected_at: date | None = None) -> bool:
    """Whether an event is usable at a decision; detected_at cannot be after decision."""
    seen = detected_at or event_date
    return seen <= decision_date


def main():
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","adjusted_close"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")]
    px=px.sort_values(["symbol","date"]);px["ret"]=px.groupby("symbol").adjusted_close.pct_change(fill_method=None)
    alerts=px[px.ret.abs()>THRESH]
    post={}
    with (ROOT/"data/research/p8_2_1/ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):post[(r["ticker"],r["anomaly_date"])]=r["classification"]
    now=datetime.now(timezone.utc).isoformat()
    rows=[]
    for r in alerts.itertuples():
        d=r.date.date();rows.append({"ticker":r.symbol,"event_date":str(d),"source_available_at":str(d),
                                    "detected_at":str(d),"classification_updated_at":now,
                                    "rule":"ABS_DAILY_ADJUSTED_RETURN_GT_5X","post_hoc_classification":post.get((r.symbol,str(d)),"NOT_IN_3041_AUDIT"),
                                    "post_hoc_used_for_signal":False,"pit_rule_available_at":str(d)})
    with (O/"event_time_audit.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    summary={"generated_at":now,"rule_threshold_abs_daily_return":THRESH,"rows":len(rows),
             "policy":"formal E uses only event-date price rule; today's VERIFIED_* classification is never used as a historical filter",
             "post_hoc_classification_timestamp":"2026-11-09 (audit run), not historical",
             "unverified_timestamp_count":len(rows),
             "time_travel_test":"available_on(event_date, decision_date, detected_at later than decision) returns False"}
    (O/"event_time_policy.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":raise SystemExit(main())
