from __future__ import annotations
import re
import pandas as pd
from pathlib import Path

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")

def normalize_ticker(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)): return "", "MISSING_TICKER"
    if not isinstance(raw, str): return "", "INVALID_TICKER_TYPE"
    s = raw.strip().upper()
    if not s: return "", "MISSING_TICKER"
    if not SYMBOL_RE.match(s): return s, "INVALID_SYMBOL_FORMAT"
    return s, "VALID"

def load_universe(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str)
    d["ticker_raw"] = d["ticker"]
    norm = [normalize_ticker(x) for x in d["ticker"]]
    d["ticker"] = [x[0] for x in norm]
    d["ticker_status"] = [x[1] for x in norm]
    d = d.drop_duplicates(["ticker", "CIK"], keep="first").copy()
    d["security_type"] = d.security_type.fillna("UNKNOWN").str.upper()
    d["active_status"] = d.listing_status.fillna("UNKNOWN")
    d["share_class"] = ""
    d["mapping_confidence"] = d.apply(lambda r: "HIGH" if r.match_status == "MATCHED" and pd.notna(r.CIK) else "MEDIUM" if pd.notna(r.CIK) else "LOW", axis=1)
    return d.rename(columns={"CIK": "cik", "security_name": "issuer_name", "source": "mapping_source"})

