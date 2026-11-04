import json
from datetime import datetime, timezone
from pathlib import Path

SNAP = json.load(open(r'..\snap28.json', encoding='utf-16'))
OVERRIDES = {
    "NKE": {
        "shares": 1485308829, "shares_basis": "Class A + Class B",
        "as_of": "2026-09-28", "period_end": "2026-08-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320187/000032018726000193/nke-20260831.htm",
        "accession": "0000320187-26-000193", "form": "10-Q", "filed": "2026-10-02",
    },
    "BRK.B": {
        "shares": 2140710161, "shares_basis": "Class B equivalent (Class A x 1500)",
        "as_of": "2026-07-29", "period_end": "2026-06-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1067983/000119312526341032/brka-20260630.htm",
        "accession": "0001193125-26-341032", "form": "10-Q", "filed": "2026-08-10",
    },
    "NEE": {
        "shares": 2097306049, "shares_basis": "Common shares",
        "as_of": "2026-09-30", "period_end": "2026-09-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/753308/000075330826000081/nee-20260930.htm",
        "accession": "0000753308-26-000081", "form": "10-Q", "filed": "2026-10-21",
    },
    "DUK": {
        "shares": 779702193, "shares_basis": "Common shares",
        "as_of": "2026-07-31", "period_end": "2026-06-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1326160/000132616026000040/duk-20260630.htm",
        "accession": "0001326160-26-000040", "form": "10-Q", "filed": "2026-08-04",
    },
    "PLD": {
        "shares": 950513000, "shares_basis": "Common shares",
        "as_of": "2026-10-26", "period_end": "2026-09-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045609/000119312526436160/pld-20260930.htm",
        "accession": "0001193125-26-436160", "form": "10-Q", "filed": "2026-10-28",
    },
}

out = {"metadata": {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": "SEC CompanyFacts dei:EntityCommonStockSharesOutstanding + targeted filing overrides",
    "source_snapshot": "docs/research/sec_fundamentals_snapshot.json @ research/dividend-quality-p46-sector-governance",
    "note": "Latest reported share count per CIK; retain period/availability for valuation checks. Not a current quote. NKE combines Class A+B; BRK.B is Class B equivalent.",
}, "companies": {}}

for ticker, v in SNAP.items():
    cik = str(v.get("cik") or "").lstrip("0")
    p = Path(f"data/sec/cache/companyfacts_{int(cik):010d}.json")
    if not p.exists():
        out["companies"][ticker] = {"cik": v.get("cik"), "status": "COMPANYFACTS_MISSING"}
        continue
    d = json.loads(p.read_text())
    candidates = []
    for taxonomy in ("dei", "us-gaap"):
        for concept in ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"):
            facts = (d.get("facts", {}).get(taxonomy, {}).get(concept, {}) or {}).get("units", {}).get("shares", [])
            for f in facts:
                if f.get("val") is None: continue
                candidates.append((str(f.get("end") or ""), str(f.get("filed") or ""), f, taxonomy, concept))
    if not candidates:
        out["companies"][ticker] = {"cik": v.get("cik"), "status": "SHARES_FACT_MISSING"}
        continue
    candidates.sort(key=lambda x: (x[0], x[1]))
    end, filed, f, tax, concept = candidates[-1]
    accession = f.get("accn")
    record = {
        "cik": v.get("cik"), "status": "AVAILABLE", "shares": f.get("val"),
        "period_end": end, "as_of": end, "filed": filed,
        "accepted_at": f.get("accepted_at"), "accession": accession,
        "form": f.get("form"), "taxonomy": tax, "concept": concept, "unit": "shares",
        "shares_basis": "Common shares outstanding",
        "source_url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(accession or '').replace('-', '')}/"
                       if accession else None),
    }
    if ticker in OVERRIDES:
        record.update(OVERRIDES[ticker])
        record["basis_source"] = "targeted filing statement"
    out["companies"][ticker] = record

out["summary"] = {
    "companies": len(out["companies"]),
    "available": sum(1 for x in out["companies"].values() if x.get("status") == "AVAILABLE"),
    "missing": sum(1 for x in out["companies"].values() if x.get("status") != "AVAILABLE"),
    "with_accession": sum(1 for x in out["companies"].values() if x.get("accession")),
    "share_class_adjusted": sorted(OVERRIDES),
}
Path("data/research/sec_shares_outstanding_28.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(out["summary"])
