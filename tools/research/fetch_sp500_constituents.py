#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Wikipedia 抓 S&P500 成分 + Date added，输出点内宇宙依据。

输出：sp500_constituents.csv
列：Ticker, Date_Added, Sector
"""
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent.parent
OUT = REPO / "sp500_constituents.csv"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def main():
    resp = requests.get(WIKI_URL, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    print(f"columns: {list(df.columns)}")
    print(f"rows: {len(df)}")

    out_rows = []
    for _, row in df.iterrows():
        sym = str(row["Symbol"]).strip().upper().replace(".", "-")
        date_added = row.get("Date added")
        sector = row.get("GICS Sector", "")
        if not sym:
            continue
        try:
            if pd.notna(date_added):
                date_str = pd.Timestamp(date_added).strftime("%Y-%m-%d")
            else:
                date_str = ""
        except Exception:
            date_str = ""
        out_rows.append({
            "Ticker": sym,
            "Date_Added": date_str,
            "Sector": str(sector),
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"written: {OUT} ({len(out_df)} rows)")
    print(out_df.head(5).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
