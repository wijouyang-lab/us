"""As-of query used by P12.3 PIT tests."""
from __future__ import annotations

import pandas as pd


def as_of(panel: pd.DataFrame, cik: str, metric: str, asof: str) -> pd.DataFrame:
    x = panel[(panel.cik.astype(str).str.zfill(10) == str(cik).zfill(10)) & (panel.metric == metric)].copy()
    x["_known"] = x["acceptance_datetime"].fillna(x["filing_date"]).astype(str).str[:10]
    x = x[x["_known"] <= asof]
    if x.empty:
        return x
    latest = x["_known"].max()
    x = x[x["_known"] == latest]
    return x.sort_values(["acceptance_datetime", "accession"]).tail(1)
