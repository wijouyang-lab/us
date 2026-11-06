"""P7 refresh latest SEC company facts for superseded candidates.

Only facts filed on or before 2026-11-05 are used. 6-K-marked names remain
quarantined. Missing facts stay missing; old values are never copied forward.
"""
from __future__ import annotations
import argparse, csv, json, math, time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

SEL = Path("data/universe/selection")
OUT = Path("data/universe/p7")
AS_OF = date(2026, 11, 5)
UA = "wijouyang-us-research/1.0 (contact: project-owner)"
TAGS = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    "net_income": ("NetIncomeLoss",),
    "equity": ("StockholdersEquity",),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
}
FORMS = {"10-K", "10-Q", "20-F", "40-F", "6-K"}


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def latest_fact(facts, tags):
    best = None
    for tag in tags:
        node = facts.get(tag)
        if not node: continue
        for unit, arr in (node.get("units") or {}).items():
            if unit != "USD": continue
            for e in arr:
                try:
                    end = date.fromisoformat(str(e.get("end"))[:10])
                    filed = date.fromisoformat(str(e.get("filed"))[:10])
                except (TypeError, ValueError):
                    continue
                if end > AS_OF or filed > AS_OF: continue
                if not e.get("form") or e["form"] not in FORMS: continue
                key = (end, filed, str(e.get("accn", "")))
                if best is None or key > best[0]: best = (key, e, tag)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="fetch SEC companyfacts over network")
    a = ap.parse_args()
    audit = read(SEL / "filing_freshness_audit_p617.csv")
    sup = {}
    for r in audit:
        if r["audit_status"] == "SUPERSEDED_BY_NEW_PERIODIC_FILING":
            sup.setdefault(r["ticker"], r)
    six = {r["ticker"] for r in audit if r["audit_status"] == "6K_LATER_NOT_VERIFIED"}
    rows = []
    for t, r in sorted(sup.items()):
        cik = r["cik"].zfill(10)
        vals = {}; meta = {}
        status = "DATA_BLOCKED"; reason = ""
        if t in six:
            status = "SIX_K_QUARANTINED"; reason = "6K_CONTENT_NOT_CONFIRMED"
        elif a.fetch:
            try:
                url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
                resp = requests.get(url, headers={"User-Agent": UA}, timeout=40)
                if resp.status_code != 200: raise RuntimeError(f"HTTP_{resp.status_code}")
                data = resp.json().get("facts", {}).get("us-gaap", {})
                for name, tags in TAGS.items():
                    best = latest_fact(data, tags)
                    if best:
                        _, e, tag = best
                        vals[name] = num(e.get("val"))
                        meta[name] = {"tag": tag, "period": e.get("end"), "filed": e.get("filed"),
                                      "form": e.get("form"), "accession": e.get("accn"), "unit": "USD"}
                present = sum(1 for x in vals.values() if x is not None)
                if present >= 3: status, reason = "UPDATED_FROM_SEC_COMPANYFACTS", ""
                elif present: status, reason = "PARTIAL_SEC_COMPANYFACTS", "LESS_THAN_3_METRICS"
                else: status, reason = "DATA_BLOCKED", "NO_USABLE_SEC_FACTS"
            except Exception as exc:
                status = "DATA_BLOCKED"; reason = f"{type(exc).__name__}:{str(exc)[:100]}"
            time.sleep(0.16)
        else:
            status = "DATA_BLOCKED"; reason = "COMPANYFACTS_REFRESH_NOT_REQUESTED"
        fcf = vals.get("cfo") - abs(vals["capex"]) if vals.get("cfo") is not None and vals.get("capex") is not None else None
        rows.append({"ticker": t, "cik": r["cik"], "old_period": r["stored_period"], "old_filed": r["stored_filed"],
                     "old_accession": r.get("stored_accession", ""),
                     "latest_periodic_form": r.get("latest_periodic_form", ""),
                     "latest_periodic_filed": r.get("latest_periodic_filed", ""),
                     "latest_periodic_accession": r.get("latest_periodic_accession", ""),
                     "new_period": max([m["period"] for m in meta.values()], default=""),
                     "new_filed": max([m["filed"] for m in meta.values()], default=""),
                     "revenue": vals.get("revenue", ""), "net_income": vals.get("net_income", ""),
                     "equity": vals.get("equity", ""), "cfo": vals.get("cfo", ""), "capex": vals.get("capex", ""),
                     "fcf": fcf if fcf is not None else "", "refresh_status": status, "refresh_reason": reason,
                     "source": "SEC companyfacts" if a.fetch else "not_requested",
                     "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json" if a.fetch else "",
                     "retrieved_at": datetime.now(timezone.utc).isoformat() if a.fetch else ""})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "updated_fundamentals.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "superseded_rows": len(rows), "status_counts": {}, "fetch": a.fetch,
               "note": "Old values are not carried forward; unavailable facts stay missing. 6-K names quarantined."}
    from collections import Counter
    summary["status_counts"] = dict(Counter(r["refresh_status"] for r in rows))
    (OUT / "updated_fundamentals_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
