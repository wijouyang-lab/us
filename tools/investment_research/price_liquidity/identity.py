from __future__ import annotations
import pandas as pd
from pathlib import Path

def load_universe(path: Path) -> pd.DataFrame:
    d=pd.read_csv(path,dtype=str)
    d["ticker"]=d.ticker.str.upper().str.strip()
    d=d.drop_duplicates("ticker").copy()
    d["security_type"]=d.security_type.fillna("UNKNOWN").str.upper()
    d["active_status"]=d.listing_status.fillna("UNKNOWN")
    d["share_class"]=""
    d["mapping_confidence"]=d.apply(lambda r:"HIGH" if r.match_status=="MATCHED" and pd.notna(r.CIK) else "MEDIUM" if pd.notna(r.CIK) else "LOW",axis=1)
    return d.rename(columns={"CIK":"cik","security_name":"issuer_name","source":"mapping_source"})
