#!/usr/bin/env python3
"""Refresh QQQ/SPY/BIL daily data with append-only provenance.

Never silently changes an already-recorded session. A mismatch fails closed.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np
import yfinance as yf

DIR = Path("data/research/qqq_transition_paper")
SPECS = {"QQQ": "2006-01-01", "SPY": "2006-01-01", "BIL": "2007-05-30"}
COLS = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]


def fetch(ticker: str, start: str) -> pd.DataFrame:
    yf.cache.set_cache_location(tempfile.mkdtemp())
    d = yf.Ticker(ticker).history(start=start, end=datetime.now(timezone.utc).date().isoformat(),
                                  auto_adjust=False)
    d = d.reset_index()
    d.columns = [str(c) for c in d.columns]
    d = d.rename(columns={"Adj Close": "Adj Close"})
    need = ["Date", "Open", "Close", "Adj Close"]
    if any(c not in d for c in need):
        raise RuntimeError(f"{ticker}: yfinance missing columns")
    out = d.copy()
    out["Date"] = pd.to_datetime(out["Date"], utc=True).dt.tz_convert(None).dt.normalize()
    for c in ("Open", "Close", "Adj Close"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
        if not out[c].map(lambda x: pd.notna(x) and x > 0).all():
            raise RuntimeError(f"{ticker}: invalid {c}")
    out = out.sort_values("Date")
    if out.Date.duplicated().any():
        raise RuntimeError(f"{ticker}: duplicate dates")
    return out


def row_hash(r) -> str:
    payload = f"{r.Date.date()}|{float(r.Open):.10f}|{float(r.Close):.10f}|{float(r['Adj Close']):.10f}"
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    fetched = {t: fetch(t, s) for t, s in SPECS.items()}
    vint_path = DIR / "vintages.jsonl"
    existing_vint = set()
    if vint_path.exists():
        for line in vint_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                existing_vint.add(rec["date"] + "|" + rec["ticker"])
    records = []
    conflicts = 0
    for t, new in fetched.items():
        path = DIR / f"{t}.csv"
        added = False
        if path.exists():
            old = pd.read_csv(path)
            old["Date"] = pd.to_datetime(old["Date"], utc=True).dt.tz_convert(None).dt.normalize()
            merged = old.copy()
            for _, r in new.iterrows():
                if r.Date in set(old.Date):
                    prev = old[old.Date == r.Date].iloc[0]
                    for c in ("Open", "Close", "Adj Close"):
                        if abs(float(prev[c]) - float(r[c])) > 1e-6:
                            conflicts += 1
                            break
                    continue
                merged = pd.concat([merged, pd.DataFrame([r])], ignore_index=True)
                added = True
            merged = merged.sort_values("Date").drop_duplicates("Date")
        else:
            merged = new
            added = True
        if added:
            merged.to_csv(path, index=False)
        for _, r in new.iterrows():
            if r.Date.date().isoformat() + "|" + t in existing_vint:
                continue
            records.append({"date": r.Date.date().isoformat(), "ticker": t,
                            "source": "yfinance", "asof": r.Date.date().isoformat(),
                            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                            "row_sha256": row_hash(r)})
    if records:
        with vint_path.open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    if not records and (DIR / "manifest.json").exists():
        print(json.dumps(json.loads((DIR / "manifest.json").read_text()), indent=2))
        return
    common_asof = min(x.Date.max() for x in fetched.values()).date().isoformat()
    manifest = {"source": "yfinance", "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "asof": common_asof,
                "existing_session_conflicts_preserved": conflicts,
                "files": {}}
    valid_dates = {}
    for t in SPECS:
        p = DIR / f"{t}.csv"
        df = pd.read_csv(p)
        dates = pd.to_datetime(df.Date, utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
        ok = (dates.notna() & np.isfinite(pd.to_numeric(df["Open"], errors="coerce")) &
              np.isfinite(pd.to_numeric(df["Close"], errors="coerce")) &
              np.isfinite(pd.to_numeric(df["Adj Close"], errors="coerce")))
        valid_dates[t] = set(dates[ok].dt.date)
        manifest["files"][t] = {"rows": len(df), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                "min_date": str(pd.to_datetime(df.Date, utc=True).min().date()),
                                "max_date": str(pd.to_datetime(df.Date, utc=True).max().date())}
    common = set.intersection(*valid_dates.values())
    if not common:
        raise RuntimeError("no common complete session across QQQ/BIL/SPY")
    manifest["asof"] = max(common).isoformat()
    manifest["common_complete_sessions"] = len(common)
    (DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
