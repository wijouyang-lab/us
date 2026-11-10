#!/usr/bin/env python3
"""Historical index membership with explicit provenance and confidence.

Default PIT admission is fail-closed: third-party medium-confidence membership
is not eligible for formal PIT research.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date as Date
from pathlib import Path

import pandas as pd

SOURCE = "fja05680/sp500"
CONFIDENCE = "third_party_medium"
PIT_ALLOWED_CONFIDENCE = {"official", "third_party_high"}


@dataclass(frozen=True)
class Member:
    ticker: str
    company_identifier: str | None
    index: str
    effective_start_date: str | None
    effective_end_date: str | None
    source: str
    source_confidence: str
    membership_status: str
    evidence_note: str
    pit_eligible: bool


def load_snapshots(path: str | Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date", "tickers"]).sort_values("date")
    d["tickers"] = d["tickers"].astype(str).str.split(",")
    return d.reset_index(drop=True)


def build_intervals(snapshots: pd.DataFrame, index: str = "SP500") -> pd.DataFrame:
    rows = []
    for _, r in snapshots.iterrows():
        for t in r["tickers"]:
            t = str(t).strip().upper()
            if t:
                rows.append({"ticker": t, "date": r["date"], "index": index})
    d = pd.DataFrame(rows).sort_values(["ticker", "date"])
    out = []
    for t, g in d.groupby("ticker"):
        dates = g["date"].tolist()
        start = dates[0]
        prev = dates[0]
        for dt in dates[1:]:
            # consecutive snapshot presence; gap > 7 days starts a new interval
            if (dt - prev).days > 7:
                out.append((t, start, prev))
                start = dt
            prev = dt
        out.append((t, start, prev))
    return pd.DataFrame(out, columns=["ticker", "effective_start", "effective_end"])


class HistoricalUniverse:
    def __init__(self, path: str | Path, *, index: str = "SP500"):
        self.snapshots = load_snapshots(path)
        self.index = index
        self.intervals = build_intervals(self.snapshots, index)
        self.last_snapshot = self.snapshots["date"].max()

    def query(self, date: str | Date, *, max_staleness_days: int = 7) -> dict:
        dt = pd.Timestamp(date)
        prev = self.snapshots[self.snapshots["date"] <= dt]
        if prev.empty:
            return {"date": str(dt.date()), "index": self.index, "members": [],
                    "status": "NO_COVERAGE", "source": SOURCE, "confidence": CONFIDENCE,
                    "pit_eligible": False, "missing_reason": "before_first_snapshot"}
        snap = prev.iloc[-1]
        stale = (dt - snap["date"]).days
        members = []
        for t in sorted({str(x).strip().upper() for x in snap["tickers"] if str(x).strip()}):
            iv = self.intervals[(self.intervals.ticker == t) & (self.intervals.effective_start <= snap["date"]) &
                                (self.intervals.effective_end >= snap["date"])]
            members.append(Member(t, None, self.index,
                                  iv.effective_start.min().date().isoformat() if len(iv) else None,
                                  iv.effective_end.max().date().isoformat() if len(iv) else None,
                                  SOURCE, CONFIDENCE, "member",
                                  f"snapshot={snap.date.date().isoformat()}; ticker identity unverified",
                                  False))
        return {"date": str(dt.date()), "index": self.index, "snapshot_date": snap.date.date().isoformat(),
                "members": [asdict(m) for m in members], "member_count": len(members),
                "status": "STALE_SNAPSHOT" if stale > max_staleness_days else "OK",
                "source": SOURCE, "confidence": CONFIDENCE, "stale_days": stale,
                "pit_eligible": False,
                "missing_reason": "stale_membership_snapshot" if stale > max_staleness_days else None}

    def get_historical_universe(self, date: str | Date, *, pit_only: bool = False) -> set[str]:
        q = self.query(date)
        if pit_only and not q["pit_eligible"]:
            return set()
        return {m["ticker"] for m in q["members"]}
