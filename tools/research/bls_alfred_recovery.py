#!/usr/bin/env python3
"""Recover ALFRED vintage data and build date-only BLS events.

No BLS HTML/PDF is fetched: the live BLS host returns HTTP 403. ALFRED is used
only for vintage observations; no embargo time is inferred from release dates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import requests

SERIES = {
    "CPIAUCSL": "cpi_headline_sa",
    "CPILFESL": "cpi_core_sa",
    "PAYEMS": "payrolls_sa",
    "UNRATE": "unemployment_sa",
    "CES0500000003": "earnings_sa",
}
BASE = "https://alfred.stlouisfed.org/series/downloaddata?seid={}"


def fetch(series: str, cache: Path, start="2006-01-01", end="2026-10-01"):
    cache.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    html = s.get(BASE.format(series), timeout=60).text
    dates = re.findall(r'<option value="(\d{4}-\d{2}-\d{2})"', html)
    if not dates:
        raise RuntimeError(f"no vintages for {series}")
    data = [
        ("form[units]", "lin"), ("form[obs_start_date]", start),
        ("form[obs_end_date]", end), ("form[file_type]", "2"),
        ("form[file_format]", "csv"), ("form[download_data]", "Download data"),
    ] + [("form[selected_vintage_dates][]", d) for d in dates]
    r = s.post(BASE.format(series), data=data, timeout=120)
    zpath = cache / f"{series}.zip"
    zpath.write_bytes(r.content)
    if not r.content.startswith(b"PK"):
        raise RuntimeError(f"{series}: no zip ({r.status_code}, {len(r.content)})")
    with zipfile.ZipFile(zpath) as z:
        name = [n for n in z.namelist() if n.endswith(".csv")][0]
        z.extract(name, cache)
    return cache / name, hashlib.sha256(zpath.read_bytes()).hexdigest(), dates


def initial_events(csv_path: Path, family: str):
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    cols = list(df.columns)
    # ALFRED column names: SERIES_YYYYMMDD
    dates = [pd.Timestamp(re.search(r"(\d{8})$", c).group(1)) for c in cols]
    rows = []
    for obs, row in df.iterrows():
        first = None
        for i, v in enumerate(row):
            if pd.notna(v):
                first = (dates[i], float(v), i)
                break
        if first is None:
            continue
        release, value, idx = first
        prior = None
        prior_year = None
        # Both prior month and prior year must come from this same vintage.
        prev_obs = obs - pd.offsets.MonthBegin(1)
        if prev_obs in df.index:
            pv = df.loc[prev_obs].iloc[idx]
            if pd.notna(pv):
                prior = float(pv)
        py_obs = obs - pd.offsets.DateOffset(years=1)
        if py_obs in df.index:
            pyv = df.loc[py_obs].iloc[idx]
            if pd.notna(pyv):
                prior_year = float(pyv)
        rows.append({"series": family, "reference_period": obs.strftime("%Y-%m"),
                     "release_date": release.date().isoformat(),
                     "initial_value": value, "prior_value_same_vintage": prior,
                     "prior_year_value_same_vintage": prior_year,
                     "vintage_column": cols[idx], "vintage_index": idx})
    return pd.DataFrame(rows)


def build(cache: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    all_series = []
    manifest = {"series": {}, "bls_live": {"cpi": 403, "empsit": 403},
                "timestamp_policy": "date_only; no inferred 08:30"}
    for sid, fam in SERIES.items():
        start = "2010-01-01" if sid == "CES0500000003" else "2006-01-01"
        path, sha, dates = fetch(sid, cache, start=start)
        e = initial_events(path, fam)
        all_series.append(e)
        manifest["series"][sid] = {"family": fam, "csv": path.name, "zip_sha256": sha,
                                   "vintages": len(dates), "first_vintage": dates[0],
                                   "last_vintage": dates[-1], "observations": len(e)}
    panel = pd.concat(all_series, ignore_index=True)
    panel.to_csv(out / "alfred_initial_values.csv", index=False)
    # Event table: one row per release date/family; only date-only timestamps.
    cpi = panel[panel.series.isin(["cpi_headline_sa", "cpi_core_sa"])].pivot_table(
        index="release_date", columns="series", values="initial_value", aggfunc="first")
    emp = panel[panel.series.isin(["payrolls_sa", "unemployment_sa", "earnings_sa"])].pivot_table(
        index="release_date", columns="series", values="initial_value", aggfunc="first")
    events = []
    for d, r in cpi.iterrows():
        events.append({"event_id": f"cpi_{d}", "event_type": "cpi", "reference_period": "",
                       "release_date": d, "embargo_time_local": "", "timezone": "America/New_York",
                       "timestamp_precision": "date_only", "timestamp_confidence": "none",
                       "scheduled_release_time": "", "actual_publication_time": "",
                       "collector_first_seen_at": "", "source_url": "https://alfred.stlouisfed.org/",
                       "source_filename": "ALFRED CPIAUCSL/CPILFESL vintages",
                       "source_sha256": manifest["series"]["CPIAUCSL"]["zip_sha256"],
                       "release_number": "", "initial_headline_value": r.get("cpi_headline_sa", ""),
                       "initial_core_value": r.get("cpi_core_sa", ""), "data_quality_status": "ALFRED_VINTAGE_DATE_ONLY"})
    for d, r in emp.iterrows():
        events.append({"event_id": f"empsit_{d}", "event_type": "employment", "reference_period": "",
                       "release_date": d, "embargo_time_local": "", "timezone": "America/New_York",
                       "timestamp_precision": "date_only", "timestamp_confidence": "none",
                       "scheduled_release_time": "", "actual_publication_time": "",
                       "collector_first_seen_at": "", "source_url": "https://alfred.stlouisfed.org/",
                       "source_filename": "ALFRED PAYEMS/UNRATE/CES0500000003 vintages",
                       "source_sha256": manifest["series"]["PAYEMS"]["zip_sha256"],
                       "release_number": "", "initial_payroll_change": r.get("payrolls_sa", ""),
                       "initial_unemployment_rate": r.get("unemployment_sa", ""),
                       "initial_earnings_mom": r.get("earnings_sa", ""), "data_quality_status": "ALFRED_VINTAGE_DATE_ONLY"})
    ev = pd.DataFrame(events).sort_values(["release_date", "event_type"])
    ev.to_csv(out / "bls_macro_events.csv", index=False)
    manifest["events"] = len(ev)
    manifest["cpi_events"] = int((ev.event_type == "cpi").sum())
    manifest["employment_events"] = int((ev.event_type == "employment").sum())
    manifest["exact_embargo_time_events"] = 0
    manifest["initial_value_coverage"] = float(ev[["initial_headline_value", "initial_payroll_change"]].notna().any(axis=1).mean())
    (out / "bls_source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache", type=Path, default=Path("data/_download/alfred"))
    p.add_argument("--out", type=Path, default=Path("data/research/macro_cross_sectional"))
    a = p.parse_args()
    print(json.dumps(build(a.cache, a.out), indent=2))
