"""P4.7.2 offline audit with SEC index roles, normalized-text offsets and
parameterized snapshot/mapping. No network imports or calls."""
from __future__ import annotations
import hashlib, json, re, html, unicodedata
from pathlib import Path
from collections import Counter
from tools.investment_research.dividend.dividend_event_parser_p44 import parse, is_false_positive
from tools.investment_research.dividend.sec_filing_fetcher import extract_split_text

CACHE = Path("data/sec/filings_p43")
OUT = Path("data/research/dividend_cache_audit_p47.json")
DEFAULT_SNAP = Path("docs/research/sec_fundamentals_snapshot.json")
NORM_VERSION = "normalized_text_v1"

ALIASES = {
    "union pacific corporation":"UNP", "nike, inc.":"NKE", "salesforce.com, inc.":"CRM", "salesforce.com":"CRM",
    "salesforce, inc.":"CRM", "apple inc.":"AAPL", "duke energy corporation":"DUK",
    "alphabet inc.":"GOOGL", "modernatx, inc.":"MRNA", "moderna, inc.":"MRNA",
}


def load_snapshot(path=DEFAULT_SNAP):
    return json.loads(Path(path).read_text())


def norm_text(raw: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip()


def role_for(item: dict, filename: str) -> dict:
    typ = str(item.get("type") or "").upper().strip()
    desc = str(item.get("description") or "").strip()
    if typ in {"8-K","8-K/A","10-K","10-K/A","10-Q","10-Q/A","20-F","40-F","6-K"}:
        return {"document_role":"PRIMARY","document_role_source":"SEC_INDEX_TYPE","document_role_confidence":"high"}
    if typ.startswith("EX-99"):
        return {"document_role":"EXHIBIT","document_role_source":"SEC_INDEX_TYPE","document_role_confidence":"high"}
    if typ.startswith("EX-"):
        return {"document_role":"OTHER_EXHIBIT","document_role_source":"SEC_INDEX_TYPE","document_role_confidence":"high"}
    if typ in {"GRAPHIC","XML","JSON","EXCEL","ZIP","IMAGE"}:
        return {"document_role":"ANCILLARY","document_role_source":"SEC_INDEX_TYPE","document_role_confidence":"high"}
    low = filename.lower()
    if "ex99-1" in low or "ex991" in low or "ex-99.1" in low or "ex99.1" in low:
        return {"document_role":"EXHIBIT","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if "ex99" in low or "ex-99" in low:
        return {"document_role":"OTHER_EXHIBIT","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if "ex10" in low or "ex-10" in low or "exhibit10" in low:
        return {"document_role":"OTHER_EXHIBIT","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if any(x in low for x in ("8k", "8-k", "10k", "10-k", "10q", "10-q")):
        return {"document_role":"PRIMARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if "index" in low:
        return {"document_role":"ANCILLARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if "earningsrelease" in low or "exhibit991" in low:
        return {"document_role":"EXHIBIT","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if "ex-2" in low or "ex-21" in low or "exhibit21" in low:
        return {"document_role":"OTHER_EXHIBIT","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if re.match(r"^[a-z]{1,5}-\d{8}\.htm$", low):
        return {"document_role":"PRIMARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if low.startswith(("cat-", "nee-", "goog-", "unp-", "nke-", "a8-k", "form10k", "d648", "d835", "d176")):
        return {"document_role":"PRIMARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if low.startswith("r") and low.endswith(".htm"):
        return {"document_role":"ANCILLARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    if low.endswith((".xml",".xsd",".jpg",".png",".css",".js",".zip")):
        return {"document_role":"ANCILLARY","document_role_source":"FILENAME_INFERENCE","document_role_confidence":"low"}
    return {"document_role":"UNKNOWN","document_role_source":"UNKNOWN","document_role_confidence":"none"}


def read_docs(d: Path):
    idx = d / "index.json"; items = []
    if idx.exists():
        try: items = json.loads(idx.read_text()).get("directory", {}).get("item", [])
        except Exception: items = []
    by_name = {str(x.get("name","")): x for x in items}
    names = [n for n in by_name if n.lower().endswith((".htm",".html"))]
    if not names:  # index missing: discover local HTML
        names = [p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".htm",".html")]
    names = list(dict.fromkeys(names))
    docs = []
    for n in names:
        p = d / n
        if not p.exists(): continue
        raw = p.read_bytes(); item = by_name.get(n, {})
        role = role_for(item, n)
        docs.append({"name": n, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                     "raw": raw.decode("utf-8","ignore"), "text": norm_text(raw.decode("utf-8","ignore")),
                     "index_document_type": item.get("type"), "index_description": item.get("description"),
                     "sequence": item.get("sequence"), **role})
    return docs


def accession_map(snapshot, split_file="data/research/split_evidence_p43.json"):
    out = {}
    try:
        for x in json.loads(Path(split_file).read_text()):
            for e in x.get("events", []):
                if e.get("accession_number"):
                    out[e["accession_number"].replace("-","")] = {"ticker":x.get("ticker"),"cik":x.get("cik"),
                        "form":None,"mapping_method":"split_evidence","mapping_confidence":"high",
                        "mapping_source_filename":split_file,"mapping_source_sha256":None}
    except Exception: pass
    for t,a in snapshot.items():
        cik=a.get("cik"); p=Path(f"data/sec/cache/submissions_{cik}.json")
        if not p.exists(): continue
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        r=json.loads(p.read_text()).get("filings",{}).get("recent",{})
        for acc,form in zip(r.get("accessionNumber",[]),r.get("form",[])):
            if acc: out[acc.replace("-","")]={"ticker":t,"cik":cik,"form":form,
                "mapping_method":"submissions_recent","mapping_confidence":"high",
                "mapping_source_filename":str(p),"mapping_source_sha256":sha}
    return out


def infer_meta(accession, docs, snapshot):
    prefix=accession[:10]; text=" ".join(d["text"] for d in docs).lower()
    names={}
    for t,a in snapshot.items():
        n=(a.get("company_name") or "").lower()
        if n: names[n]=t
    for n,t in ALIASES.items():
        if t in snapshot: names[n]=t
    matches=[(n,t) for n,t in names.items() if n and n in text]
    if matches:
        longest=max(len(n) for n,_ in matches)
        top={t for n,t in matches if len(n)==longest}
        d=next((x for x in docs if any(n in x["text"].lower() for n,_ in matches)), docs[0] if docs else {})
        if len(top)==1:
            t=top.pop(); cik=snapshot[t].get("cik")
            return {"ticker":t,"cik":cik,"form":None,"submitter_cik_hint":prefix,"issuer_cik":cik,
                    "mapping_method":"local_primary_name","mapping_confidence":"high",
                    "mapping_source_filename":d.get("name"),"mapping_source_sha256":d.get("sha256")}
        return {"ticker":None,"cik":None,"form":None,"submitter_cik_hint":prefix,"issuer_cik":None,
                "mapping_method":"AMBIGUOUS_NAME_MATCH","mapping_confidence":"none",
                "candidate_tickers":sorted(top),
                "mapping_source_filename":d.get("name"),"mapping_source_sha256":d.get("sha256")}
    return {"ticker":None,"cik":None,"form":None,"submitter_cik_hint":prefix,"issuer_cik":None,
            "mapping_method":"UNMAPPED","mapping_confidence":"none",
            "mapping_source_filename":docs[0]["name"] if docs else None,
            "mapping_source_sha256":docs[0]["sha256"] if docs else None}


def locate(text: str, needle: str | None):
    if not needle: return {"location_status":"LOCATION_UNRESOLVED"}
    hits=[m.start() for m in re.finditer(re.escape(needle), text, re.I)]
    if len(hits)!=1: return {"location_status":"LOCATION_AMBIGUOUS","occurrences":len(hits)}
    i=hits[0]; j=i+len(needle)
    return {"location_status":"OK","start_char":i,"end_char":j,"matched_text":text[i:j],
            "context_before":text[max(0,i-80):i],"context_after":text[j:j+80],
            "text_normalization_version":NORM_VERSION}


def audit(cache_dir=CACHE, snapshot_path=DEFAULT_SNAP, mapping_registry=None):
    if not Path(cache_dir).exists():
        return {"status":"LEGACY_CACHE_UNAVAILABLE","provenance_status":"LEGACY_PLACEHOLDER_UA",
                "evidence_status":"PRELIMINARY_ONLY","accession_count":0,"status_counts":{},
                "accessions":[],"candidates":[],"split_mentions":[],"special":{}}
    snap=load_snapshot(snapshot_path); amap=accession_map(snap)
    if mapping_registry:
        amap.update(mapping_registry)
    rows=[]; counts=Counter(); candidates=[]; splits=[]
    for d in sorted(p for p in Path(cache_dir).iterdir() if p.is_dir()):
        acc=d.name; docs=read_docs(d); meta=amap.get(acc) or infer_meta(acc,docs,snap)
        meta.setdefault("submitter_cik_hint",acc[:10]); meta.setdefault("issuer_cik",meta.get("cik"))
        primaries=[x for x in docs if x["document_role"]=="PRIMARY"]
        primary=primaries[0] if primaries else next((x for x in docs if x["document_role"]=="EXHIBIT"),None)
        exhibits=[x for x in docs if x["document_role"] in ("EXHIBIT","OTHER_EXHIBIT")]
        status="PRIMARY_CACHED" if primary else "MISSING_LOCAL_FILE"
        if exhibits and not primaries: status="EXHIBIT_CACHED"
        ptext=primary["text"].lower() if primary else ""
        if primary and not exhibits:
            if re.search(r"ex(?:hibit)?\s*99(?:\.1)?", ptext): status="EXHIBIT_99_REFERENCED"
            elif re.search(r"ex(?:hibit)?\s*[0-9]+", ptext): status="OTHER_EXHIBIT_REFERENCED"
            elif "attached" in ptext: status="ATTACHMENT_REFERENCE_UNSPECIFIED"
            else: status="NO_EXHIBIT_REFERENCE"
        counts[status]+=1
        rows.append({"accession":acc,**meta,"provenance_status":"LEGACY_PLACEHOLDER_UA",
            "evidence_status":"PRELIMINARY_ONLY","status":status,
            "documents":[{k:v for k,v in x.items() if k not in ("raw","text")} for x in docs],
            "primary":primary["name"] if primary else None,"exhibits":[x["name"] for x in exhibits]})
        for doc in docs:
            if doc["document_role"] not in ("PRIMARY","EXHIBIT","OTHER_EXHIBIT"): continue
            for ev in parse(doc["text"],ticker=meta.get("ticker") or "UNKNOWN",cik=meta.get("cik") or "",
                            source_url="LOCAL_CACHE",accession=acc,evidence_sha256=doc["sha256"]):
                needle=(f"${ev['declared_per_share']:.2f}" if ev.get("declared_per_share") is not None else "dividend")
                ev.update({"evidence_status":"PRELIMINARY_LEGACY_CACHE","verification_status":"PRELIMINARY_ONLY",
                    "is_event":False,"source_filename":doc["name"],"source_sha256":doc["sha256"],
                    "source_document_role":doc["document_role"],
                    "source_text_location":locate(doc["text"],needle),
                    "candidate_type":("PRELIMINARY_8K_CANDIDATE" if meta.get("form")=="8-K" and ev.get("announcement_date")
                                      else "HISTORICAL_DIVIDEND_CONTEXT")})
                candidates.append(ev)
            fp=is_false_positive(doc["text"])
            if fp:
                candidates.append({"ticker":meta.get("ticker"),"accession":acc,"is_event":False,
                    "evidence_status":"PRELIMINARY_LEGACY_CACHE","verification_status":"PRELIMINARY_ONLY",
                    "candidate_type":"FALSE_POSITIVE","source_filename":doc["name"],"source_sha256":doc["sha256"],
                    "source_document_role":doc["document_role"],"source_text_location":locate(doc["text"],"67.75"),**fp})
            sp=extract_split_text(doc["text"])
            if sp.get("ratio") or sp.get("mentions_split"):
                splits.append({"ticker":meta.get("ticker"),"accession":acc,"ratio":sp.get("ratio"),
                    "dates":sp.get("dates"),"evidence_status":"PRELIMINARY_LEGACY_CACHE",
                    "source_filename":doc["name"],"source_sha256":doc["sha256"],
                    "source_document_role":doc["document_role"],
                    "source_text_location":locate(doc["text"],"split"),
                    "status":"PARTIALLY_VERIFIED"})
    role_counts=Counter(d["document_role"] for r in rows for d in r["documents"])
    return {"status":"LEGACY_CACHE_PRESENT","generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "provenance_status":"LEGACY_PLACEHOLDER_UA","evidence_status":"PRELIMINARY_ONLY",
        "cache_path":str(cache_dir),"accession_count":len(rows),"status_counts":dict(counts),
        "document_role_counts":dict(role_counts),"accessions":rows,"candidates":candidates,
        "split_mentions":splits,"special":{t:[r for r in rows if r.get("ticker")==t] for t in ("CAT","BAC","NEE")}}


if __name__ == "__main__":
    a=audit(); OUT.write_text(json.dumps(a,indent=2,default=str),encoding="utf-8")
    print("accessions",a["accession_count"],a["status_counts"],"roles",a["document_role_counts"],"candidates",len(a["candidates"]))
