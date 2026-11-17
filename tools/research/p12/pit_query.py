"""As-of PIT query over accession-level facts.

Each fact identity is (CIK, metric, taxonomy, tag, unit, period_start, period_end).
For every identity, return the latest version known by the query timestamp.
"""
from __future__ import annotations

import pandas as pd

IDENTITY = ["cik", "metric", "taxonomy", "tag", "unit", "period_start", "period_end"]


def _known(row) -> pd.Timestamp:
    if pd.notna(row.get("acceptance_datetime")) and str(row.get("acceptance_datetime")):
        return pd.to_datetime(row["acceptance_datetime"], utc=True)
    # Filing date has day precision only: use end of day and mark low precision.
    d = pd.to_datetime(row["filing_date"], utc=True)
    return d + pd.Timedelta(hours=23, minutes=59, seconds=59)


def as_of(panel: pd.DataFrame, cik: str, metric: str, asof: str) -> pd.DataFrame:
    x = panel[panel.cik.astype(str).str.zfill(10) == str(cik).zfill(10)]
    x = x[x.metric == metric].copy()
    if x.empty:
        return x
    x["_known"] = x.apply(_known, axis=1)
    x["_precision"] = x["acceptance_datetime"].apply(lambda v: "ACCEPTANCE_TIMESTAMP" if pd.notna(v) and str(v) else "FILING_DATE_LOW_PRECISION")
    x["identity_key"] = x[IDENTITY].astype(str).agg("|".join, axis=1)
    q = pd.to_datetime(asof, utc=True)
    if len(str(asof)) == 10:
        q = q + pd.Timedelta(hours=23, minutes=59, seconds=59)
    x = x[x["_known"] <= q]
    if x.empty:
        return x
    out = (x.sort_values(["_known", "accession"])
           .groupby("identity_key", as_index=False)
           .tail(1)
           .sort_values(["period_end", "identity_key"]))
    out = out.rename(columns={"_known": "known_at", "_precision": "time_precision"})
    out["is_latest_visible"] = True
    return out
