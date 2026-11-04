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
NAME_TO_TICKER = {
    "union pacific corporation":"UNP", "nike, inc.":"NKE", "salesforce.com, inc.":"CRM",
    "apple inc.":"AAPL", "duke energy corporation":"DUK", "alphabet inc.":"GOOGL",
    "modernatx, inc.":"MRNA", "moderna, inc.":"MRNA",
}


def accession_map():
    out = {}
    for f in ("data/research/split_evidence_p43.json",):
        try:
            for x in json.loads(Path(f).read_text()):
                for e in x.get("events", []):
                    if e.get("accession_number"):
                        out[e["accession_number"].replace("-", "")] = {
                            "ticker": x.get("ticker"), "cik": x.get("cik"), "form": None,
                            "mapping_method": "split_evidence", "mapping_confidence": "high",
                            "mapping_source_filename": f, "mapping_source_sha256": None}
        except Exception:
            pass
    for t, a in SNAP.items():
        cik = a.get("cik"); p = Path(f"data/sec/cache/submissions_{cik}.json")
        if not p.exists(): continue
        src_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        r = json.loads(p.read_text()).get("filings", {}).get("recent", {})
        for acc, form in zip(r.get("accessionNumber", []), r.get("form", [])):
            if acc:
                out[acc.replace("-", "")] = {"ticker": t, "cik": cik, "form": form,
                    "mapping_method":"submissions_recent", "mapping_confidence":"high",
                    "mapping_source_filename": str(p), "mapping_source_sha256": src_sha}
    return out


def infer_meta(accession: str, docs: list[dict]):
    prefix = accession[:10]
    text = (docs[0].get("text", "") if docs else "").lower()
    matches = [(name, ticker) for name, ticker in NAME_TO_TICKER.items() if name in text]
    if len({t for _, t in matches}) == 1:
        ticker = matches[0][1]; cik = SNAP[ticker].get("cik"); primary = docs[0] if docs else {}
        return {"ticker": ticker, "cik": cik, "form": None, "submitter_cik_hint": prefix,
                "issuer_cik": cik, "mapping_method": "local_primary_name", "mapping_confidence": "high",
                "mapping_source_filename": primary.get("name"),
                "mapping_source_sha256": primary.get("sha256")}
    return {"ticker": None, "cik": None, "form": None, "submitter_cik_hint": prefix,
            "issuer_cik": None, "mapping_method": "UNMAPPED", "mapping_confidence": "none",
            "mapping_source_filename": docs[0].get("name") if docs else None,
            "mapping_source_sha256": docs[0].get("sha256") if docs else None}


def read_docs(d: Path):
    idx = d / "index.json"; names = []
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


def audit(cache_dir: Path = CACHE, snapshot_path: Path = Path("docs/research/sec_fundamentals_snapshot.json")):
    if not Path(cache_dir).exists():
        return {"status": "LEGACY_CACHE_UNAVAILABLE", "provenance_status": "LEGACY_PLACEHOLDER_UA",
                "evidence_status": "PRELIMINARY_ONLY", "accession_count": 0, "status_counts": {},
                "accessions": [], "candidates": [], "split_mentions": [], "special": {}}
    amap = accession_map(); rows = []; counts = Counter(); candidates = []; splits = []
    for d in sorted(p for p in Path(cache_dir).iterdir() if p.is_dir()):
        acc = d.name; docs = read_docs(d)
        meta = amap.get(acc) or infer_meta(acc, docs)
        meta.setdefault("submitter_cik_hint", acc[:10]); meta.setdefault("issuer_cik", meta.get("cik"))
        primary = next((x for x in docs if not x["name"].lower().startswith("r")
                        and "ex99" not in x["name"].lower() and "ex-99" not in x["name"].lower()), None)
        exhibits = [x for x in docs if "ex99" in x["name"].lower() or "ex-99" in x["name"].lower()]
        status = "PRIMARY_CACHED" if primary else "MISSING_LOCAL_FILE"
        if exhibits and not primary: status = "EXHIBIT_CACHED"
        ptext = primary["text"].lower() if primary else ""
        if primary and not exhibits:
            if re.search(r"ex(?:hibit)?\s*99(?:\.1)?", ptext): status = "EXHIBIT_99_REFERENCED"
            elif re.search(r"ex(?:hibit)?\s*[0-9]+", ptext): status = "OTHER_EXHIBIT_REFERENCED"
            elif "attached" in ptext: status = "ATTACHMENT_REFERENCE_UNSPECIFIED"
            else: status = "NO_EXHIBIT_REFERENCE"
        counts[status] += 1
        rows.append({"accession": acc, **meta, "provenance_status": "LEGACY_PLACEHOLDER_UA",
                     "evidence_status": "PRELIMINARY_ONLY", "status": status,
                     "documents": [{k:v for k,v in x.items() if k!="text"} for x in docs],
                     "primary": primary["name"] if primary else None,
                     "exhibits": [x["name"] for x in exhibits]})
        for doc in docs:
            text = doc["text"]
            for ev in parse(text, ticker=meta.get("ticker") or "UNKNOWN", cik=meta.get("cik") or "",
                            source_url="LOCAL_CACHE", accession=acc, evidence_sha256=doc["sha256"]):
                ev.update({"evidence_status":"PRELIMINARY_LEGACY_CACHE", "verification_status":"PRELIMINARY_ONLY",
                           "is_event":False, "source_filename":doc["name"], "source_sha256":doc["sha256"],
                           "source_document_role":"PRIMARY" if doc is primary else "EXHIBIT",
                           "source_text_location":"document_text",
                           "candidate_type":("PRELIMINARY_8K_CANDIDATE" if meta.get("form")=="8-K"
                                             and ev.get("announcement_date") else "HISTORICAL_DIVIDEND_CONTEXT")})
                candidates.append(ev)
            fp = is_false_positive(text)
            if fp:
                candidates.append({"ticker":meta.get("ticker"),"accession":acc,"is_event":False,
                    "evidence_status":"PRELIMINARY_LEGACY_CACHE","verification_status":"PRELIMINARY_ONLY",
                    "candidate_type":"FALSE_POSITIVE","source_filename":doc["name"],
                    "source_sha256":doc["sha256"],"source_document_role":"PRIMARY" if doc is primary else "EXHIBIT", **fp})
            sp = extract_split_text(text)
            if sp.get("ratio") or sp.get("mentions_split"):
                splits.append({"ticker":meta.get("ticker"),"accession":acc,"ratio":sp.get("ratio"),
                    "dates":sp.get("dates"),"evidence_status":"PRELIMINARY_LEGACY_CACHE",
                    "source_filename":doc["name"],"source_sha256":doc["sha256"],
                    "source_document_role":"PRIMARY" if doc is primary else "EXHIBIT",
                    "status":"PARTIALLY_VERIFIED"})
    return {"status":"LEGACY_CACHE_PRESENT",
            "generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "provenance_status":"LEGACY_PLACEHOLDER_UA","evidence_status":"PRELIMINARY_ONLY",
            "cache_path":str(cache_dir),"accession_count":len(rows),"status_counts":dict(counts),
            "accessions":rows,"candidates":candidates,"split_mentions":splits,
            "special":{t:[r for r in rows if r.get("ticker")==t] for t in ("CAT","BAC","NEE")}}


if __name__ == "__main__":
    a = audit(); OUT.write_text(json.dumps(a, indent=2, default=str), encoding="utf-8")
    print("accessions", a["accession_count"], a["status_counts"], "candidates", len(a["candidates"]), "splits", len(a["split_mentions"]))
