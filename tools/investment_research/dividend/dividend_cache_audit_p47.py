"""P4.7 offline audit of P4.3 legacy SEC cache. No network imports/calls."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from collections import Counter
from tools.investment_research.dividend.dividend_event_parser_p44 import parse, is_false_positive
from tools.investment_research.dividend.sec_filing_fetcher import extract_split_text

CACHE = Path("data/sec/filings_p43")
OUT = Path("data/research/dividend_cache_audit_p47.json")
SNAP = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())


def accession_map():
    out = {}
    for f in ("data/research/split_evidence_p43.json",):
        try:
            for x in json.loads(Path(f).read_text()):
                for e in x.get("events", []):
                    if e.get("accession_number"):
                        out[e["accession_number"].replace("-", "")] = {"ticker": x.get("ticker"), "cik": x.get("cik")}
        except Exception: pass
    for t, a in SNAP.items():
        cik = a.get("cik"); p = Path(f"data/sec/cache/submissions_{cik}.json")
        if not p.exists(): continue
        r = json.loads(p.read_text()).get("filings", {}).get("recent", {})
        for acc, form in zip(r.get("accessionNumber", []), r.get("form", [])):
            out[acc.replace("-", "")] = {"ticker": t, "cik": cik, "form": form}
    return out


def read_docs(d: Path):
    idx = d / "index.json"
    names = []
    if idx.exists():
        try: names = [x.get("name","") for x in json.loads(idx.read_text())["directory"]["item"]]
        except Exception: names = []
    names = [n for n in names if n.lower().endswith((".htm",".html")) and "index" not in n.lower()]
    docs = []
    for n in names:
        p = d / n
        if not p.exists(): continue
        raw = p.read_bytes()
        docs.append({"name": n, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                     "text": raw.decode("utf-8", "ignore")})
    return docs


def audit():
    if not CACHE.exists():
        return {"generated_at": None, "status": "LEGACY_CACHE_UNAVAILABLE",
                "provenance_status": "LEGACY_PLACEHOLDER_UA", "evidence_status": "PRELIMINARY_ONLY",
                "accession_count": 0, "status_counts": {}, "accessions": [],
                "candidates": [], "split_mentions": [], "special": {}}
    amap = accession_map(); rows = []; counts = Counter(); candidates = []; splits = []
    for d in sorted(p for p in CACHE.iterdir() if p.is_dir()):
        acc = d.name
        meta = amap.get(acc, {}); docs = read_docs(d)
        primary = next((x for x in docs if not x["name"].lower().startswith("r")
                        and "ex99" not in x["name"].lower() and "ex-99" not in x["name"].lower()), None)
        exhibits = [x for x in docs if "ex99" in x["name"].lower() or "ex-99" in x["name"].lower()]
        status = "PRIMARY_CACHED" if primary else "MISSING_LOCAL_FILE"
        if exhibits: status = "EXHIBIT_CACHED"
        if not primary and not exhibits: status = "MISSING_LOCAL_FILE"
        ptext = primary["text"].lower() if primary else ""
        if primary and not exhibits and ("exhibit 99" in ptext or "see exhibit" in ptext or "attached" in ptext):
            status = "EXHIBIT_REQUIRED"
        counts[status] += 1
        row = {"accession": acc, "ticker": meta.get("ticker"), "cik": meta.get("cik"), "form": meta.get("form"),
               "provenance_status": "LEGACY_PLACEHOLDER_UA", "evidence_status": "PRELIMINARY_ONLY",
               "status": status, "documents": [{k:v for k,v in x.items() if k!="text"} for x in docs],
               "primary": primary["name"] if primary else None,
               "exhibits": [x["name"] for x in exhibits]}
        text = "\n".join(x["text"] for x in docs)
        # candidates from all docs
        if primary:
            for ev in parse(text, ticker=meta.get("ticker") or "UNKNOWN", cik=meta.get("cik") or "",
                            source_url="LOCAL_CACHE", accession=acc,
                            evidence_sha256=primary["sha256"]):
                ev["evidence_status"] = "PRELIMINARY_LEGACY_CACHE"
                ev["verification_status"] = "PRELIMINARY_ONLY"
                ev["is_event"] = False
                ev["candidate_type"] = ("PRELIMINARY_8K_CANDIDATE" if meta.get("form") == "8-K"
                                        and ev.get("announcement_date") else "HISTORICAL_DIVIDEND_CONTEXT")
                ev["source_filename"] = primary["name"]
                candidates.append(ev)
        fp = is_false_positive(text)
        if fp:
            candidates.append({"ticker": meta.get("ticker"), "accession": acc, "is_event": False,
                               "evidence_status": "PRELIMINARY_LEGACY_CACHE",
                               "verification_status": "PRELIMINARY_ONLY",
                               "candidate_type": "FALSE_POSITIVE", **fp})
        sp = extract_split_text(text)
        if sp.get("ratio") or sp.get("mentions_split"):
            splits.append({"ticker": meta.get("ticker"), "accession": acc, "ratio": sp.get("ratio"),
                           "dates": sp.get("dates"), "evidence_status": "PRELIMINARY_LEGACY_CACHE",
                           "sha256": primary["sha256"] if primary else None,
                           "status": "PARTIALLY_VERIFIED"})
        rows.append(row)
    return {"status": "LEGACY_CACHE_PRESENT", "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "provenance_status": "LEGACY_PLACEHOLDER_UA", "evidence_status": "PRELIMINARY_ONLY",
            "cache_path": str(CACHE), "accession_count": len(rows),
            "status_counts": dict(counts), "accessions": rows,
            "candidates": candidates, "split_mentions": splits,
            "special": {t: [r for r in rows if r.get("ticker")==t] for t in ("CAT","BAC","NEE")}}


if __name__ == "__main__":
    import datetime
    a = audit(); OUT.write_text(json.dumps(a, indent=2, default=str), encoding="utf-8")
    print("accessions", a["accession_count"], a["status_counts"], "candidates", len(a["candidates"]), "splits", len(a["split_mentions"]))
