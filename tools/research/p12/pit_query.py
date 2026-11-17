"""As-of PIT query over accession-level facts.

Filing-date-only facts are available only at the end of the US/Eastern calendar
day, converted to UTC. Full timestamps must carry an explicit timezone.
"""
from __future__ import annotations

import pandas as pd

IDENTITY = ["cik", "metric", "taxonomy", "tag", "unit", "period_start", "period_end"]
ET = "America/New_York"


def _et_end_of_day(day: str) -> pd.Timestamp:
    """End of the US/Eastern calendar day, returned in UTC."""
    local = pd.Timestamp(day).tz_localize(ET) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return local.tz_convert("UTC")


def _parse_asof(asof: str) -> pd.Timestamp:
    text = str(asof).strip()
    if len(text) == 10:
        return _et_end_of_day(text)
    ts = pd.Timestamp(text)
    if ts.tzinfo is None:
        raise ValueError("ASOF_TIMESTAMP_REQUIRES_EXPLICIT_TIMEZONE")
    return ts.tz_convert("UTC")


def _known(row) -> pd.Timestamp:
    if pd.notna(row.get("acceptance_datetime")) and str(row.get("acceptance_datetime")):
        return pd.to_datetime(row["acceptance_datetime"], utc=True)
    # Filing date has day precision only: use US/Eastern end of day.
    return _et_end_of_day(str(row["filing_date"])[:10])


def as_of(panel: pd.DataFrame, cik: str, metric: str, asof: str) -> pd.DataFrame:
    x = panel[panel.cik.astype(str).str.zfill(10) == str(cik).zfill(10)]
    x = x[x.metric == metric].copy()
    if x.empty:
        return x
    x["_known"] = x.apply(_known, axis=1)
    x["_precision"] = x["acceptance_datetime"].apply(
        lambda v: "ACCEPTANCE_TIMESTAMP" if pd.notna(v) and str(v) else "FILING_DATE_LOW_PRECISION"
    )
    x["identity_key"] = x[IDENTITY].fillna("").astype(str).agg("|".join, axis=1)
    q = _parse_asof(asof)
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
