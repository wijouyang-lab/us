"""Generate P12.3.1 as-of query evidence and quality summary."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.research.p12.pit_query import as_of

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_3_1"
PANEL = pd.read_csv(ROOT / "data/research/p12_3/p12_3_accession_fact_panel.csv", dtype={"cik": str})
PANEL["cik"] = PANEL.cik.str.zfill(10)


def one(label, cik, metric, asof):
    q = as_of(PANEL, cik, metric, asof)
    return {
        "query": label, "cik": cik, "metric": metric, "asof": asof,
        "rows": len(q), "periods": int(q.period_end.nunique()) if len(q) else 0,
        "latest_known": str(q.known_at.max()) if len(q) else "",
        "latest_accession": ",".join(q.accession.drop_duplicates().astype(str)) if len(q) else "",
        "status": "OK" if len(q) else "EMPTY",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tests = [
        one("three_plus_periods", "0000320193", "Revenue", "2015-06-30"),
        one("before_abt_revision", "0000001800", "Capex", "2018-12-31"),
        one("after_abt_revision", "0000001800", "Capex", "2019-08-01"),
        one("abt_same_day_before", "0000001800", "Capex", "2018-08-01T19:00:00Z"),
        one("abt_same_day_after", "0000001800", "Capex", "2018-08-01T21:00:00Z"),
        one("future_not_visible", "0000001800", "Capex", "2018-07-31"),
    ]
    pd.DataFrame(tests).to_csv(OUT / "p12_3_1_asof_query_tests.csv", index=False)
    print(tests)
    print("quality pending")


if __name__ == "__main__":
    main()
