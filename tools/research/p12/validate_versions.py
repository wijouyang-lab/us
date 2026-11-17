"""Spot-check 10-Q and amendment filings against raw XBRL."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import requests

from tools.research.p12.validate_raw_filings import _parse_instance

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_3_1"
H = {"User-Agent": "P12 SEC PIT pilot contact@example.com"}
TICKERS = ["AAPL", "MSFT", "JNJ", "MON", "BP"]
METRICS = ["Revenue", "NetIncome", "TotalAssets", "OperatingCashFlow"]


def main() -> int:
    panel = pd.read_csv(ROOT / "data/research/p12_3/p12_3_accession_fact_panel.csv", dtype={"cik": str})
    panel["cik"] = panel.cik.str.zfill(10)
    cache = ROOT / "cache_raw"; cache.mkdir(exist_ok=True)
    rows = []
    for t in TICKERS:
        forms = ["10-Q/A"] if t == "MON" else ["10-Q"]
        p = panel[(panel.ticker == t) & panel.form.isin(forms)].sort_values("filing_date")
        if p.empty:
            continue
        acc = p.iloc[-1].accession
        sub = p[p.accession == acc]
        meta = sub.iloc[0]
        cik = meta.cik
        idx = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/index.json"
        j = requests.get(idx, headers=H, timeout=60).json()
        names = [x["name"] for x in j["directory"]["item"]]
        xmls = [n for n in names if n.endswith(".xml") and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary)\.xml$", n)]
        if not xmls:
            rows.append({"ticker": t, "accession": acc, "status": "NO_XBRL"})
            continue
        xmln = sorted(xmls, key=lambda n: (not n.endswith("_htm.xml"), -len(n)))[0]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{xmln}"
        fp = cache / f"v31_{t}_{xmln}"
        if not fp.exists():
            fp.write_bytes(requests.get(url, headers=H, timeout=90).content)
        raw = _parse_instance(fp)
        for metric in METRICS:
            pr = sub[sub.metric == metric].dropna(subset=["value"])
            if pr.empty:
                rows.append({"ticker": t, "accession": acc, "form": meta.form, "metric": metric, "status": "PANEL_MISSING"})
                continue
            prow = pr.iloc[-1]
            cand = [f for f in raw if f["tag"] == prow.tag and f["end"] == str(prow.period_end)]
            if metric in {"Revenue", "NetIncome", "OperatingCashFlow"}:
                cand = sorted(cand, key=lambda f: (pd.to_datetime(f["end"]) - pd.to_datetime(f["start"])).days if f.get("start") else -1, reverse=True)
            if not cand:
                rows.append({"ticker": t, "accession": acc, "form": meta.form, "metric": metric, "panel_value": prow.value, "raw_value": None, "status": "RAW_MISSING"})
                continue
            rv = float(cand[0]["value"].replace(",", ""))
            pv = float(prow.value)
            pdur = (pd.to_datetime(prow.period_end) - pd.to_datetime(prow.period_start)).days if pd.notna(prow.period_start) else None
            rdur = (pd.to_datetime(cand[0]["end"]) - pd.to_datetime(cand[0]["start"])).days if cand[0].get("start") else None
            if abs(pv - rv) <= max(1, abs(pv) * 1e-6):
                status = "MATCH"
            elif pdur is not None and rdur is not None and abs(pdur - rdur) > 5:
                status = "PERIOD_AGGREGATION_MISMATCH"
            elif abs(pv - rv) <= max(1, abs(pv) * .01):
                status = "ROUNDING"
            else:
                status = "CONFLICT"
            rows.append({"ticker": t, "accession": acc, "form": meta.form, "metric": metric, "panel_value": pv, "raw_value": rv, "panel_duration_days": pdur, "raw_duration_days": rdur, "status": status, "tag": prow.tag, "period_end": prow.period_end})
    pd.DataFrame(rows).to_csv(OUT / "p12_3_1_fact_version_validation.csv", index=False)
    print(pd.Series([r["status"] for r in rows]).value_counts().to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
