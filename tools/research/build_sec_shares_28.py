import json
from pathlib import Path

snap = json.load(open(r'..\snap28.json', encoding='utf-16'))
out = {"metadata": {
    "generated_at": "2026-11-05T00:00:00Z",
    "source": "SEC CompanyFacts dei:EntityCommonStockSharesOutstanding",
    "source_snapshot": "docs/research/sec_fundamentals_snapshot.json @ research/dividend-quality-p46-sector-governance",
    "note": "Latest reported share count per CIK; retain period/availability for valuation checks. Not a current quote.",
}, "companies": {}}
for ticker, v in snap.items():
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
    out["companies"][ticker] = {"cik": v.get("cik"), "status": "AVAILABLE",
        "shares": f.get("val"), "period_end": end, "filed": filed,
        "accepted_at": f.get("accepted_at"), "accession": f.get("acc"),
        "form": f.get("form"), "taxonomy": tax, "concept": concept,
        "unit": "shares"}
out["summary"] = {"companies": len(out["companies"]),
                  "available": sum(1 for x in out["companies"].values() if x.get("status") == "AVAILABLE"),
                  "missing": sum(1 for x in out["companies"].values() if x.get("status") != "AVAILABLE")}
Path("data/research/sec_shares_outstanding_28.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(out["summary"])
print([(k, v.get("shares"), v.get("period_end")) for k, v in out["companies"].items()][:5])
