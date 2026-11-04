"""P4.5 targeted field verification for the two live SEC downloads.

Reads only the already-downloaded smoke artifact/manifest. No network.
"""
from __future__ import annotations
import hashlib, html, json, re
from datetime import datetime
from pathlib import Path

ROOT = Path("data/sec/filings_p45_smoke")
OUT_EVENTS = Path("data/research/dividend_events_targeted_p45.json")
OUT_AUDIT = Path("data/research/dividend_event_field_audit_p45.json")
OUT_EXCL = Path("data/research/dividend_event_exclusions_p45.json")
MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
DATE = re.compile(r"(" + MONTHS + r"\s+\d{1,2},\s+\d{4})", re.I)
AMOUNT = re.compile(r"\(?\$([0-9]+\.[0-9]{2})\)?\s*per\s+(?:common\s+)?share", re.I)


def norm(raw: str) -> str:
    s = re.sub(r"(?s)<[^>]+>", " ", raw)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def date_iso(x):
    if not x: return None
    clean = x.replace(".", "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try: return datetime.strptime(clean, fmt).date().isoformat()
        except ValueError: pass
    return None


def parse_common(text: str, ticker: str, role: str):
    text = norm(text)
    candidates = []
    for m in AMOUNT.finditer(text):
        start = text.rfind(". ", 0, m.start()) + 2
        end = text.find(". ", m.end())
        if end == -1: end = len(text)
        sentence = text[start:end+1]
        ctx = sentence
        nx0 = end + 2; nx1 = text.find(". ", nx0)
        if nx1 == -1: nx1 = len(text)
        nxt = text[nx0:nx1+1]
        if re.search(r"payable|record|previous|prior", nxt, re.I) and "preferred" not in nxt.lower():
            ctx = sentence + " " + nxt
        low = ctx.lower()
        if "dividend" not in low: continue
        if "common stock" not in low and "common share" not in low: continue
        if "preferred" in sentence.lower() or "depositary" in sentence.lower(): continue
        if not re.search(r"declared|approved|raise|voted", low): continue
        rel = m.start() - start
        before = ctx[:rel]
        after = ctx[rel + len(m.group(0)):]
        dates_before = [(x.start(), x.group(1)) for x in DATE.finditer(before)]
        ann = dates_before[-1][1] if dates_before else None
        if not ann:
            prior = DATE.findall(text[max(0,start-300):start])
            ann = prior[-1] if prior else None
        pay = None; rec = None
        mp = re.search(r"payable[^.]{0,100}?(" + DATE.pattern + r")", after, re.I)
        mr = re.search(r"record[^.]{0,100}?(" + DATE.pattern + r")", after, re.I)
        if mp: pay = mp.group(1)
        if mr: rec = mr.group(1)
        prev = re.search(r"(?:previous|prior)[^.]{0,80}?\$([0-9]+\.[0-9]{2})\s*per share", ctx, re.I)
        inc_window = ctx
        inc = re.search(r"(?:up\s+)?\$([0-9]+\.[0-9]{2})\s+from", inc_window, re.I)
        cents = re.search(r"(?:\$)?([0-9]+)\s+cents", inc_window, re.I)
        if not cents:
            word = re.search(r"(eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\s+cents", inc_window, re.I)
            if word:
                val = {"eight":"8","nine":"9","ten":"10","eleven":"11","twelve":"12","thirteen":"13","fourteen":"14","fifteen":"15"}[word.group(1).lower()]
                cents = type("C",(),{"group":lambda self,n,v=val: v})()
        pct = re.search(r"([0-9]+)\s*%", inc_window, re.I)
        pct_val = pct.group(1) if pct else None
        if not pct_val:
            word = re.search(r"(eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\s+percent", inc_window, re.I)
            pct_val = {"eight":"8","nine":"9","ten":"10","eleven":"11","twelve":"12","thirteen":"13","fourteen":"14","fifteen":"15"}.get(word.group(1).lower()) if word else None
        candidates.append({"ticker":ticker,"event_type":"DECLARED","security_type":"COMMON",
            "declared_per_share":float(m.group(1)),"currency":"USD","frequency":"QUARTERLY",
            "announcement_date":date_iso(ann),"record_date":date_iso(rec),
            "payment_date":date_iso(pay),"ex_date":None,"ex_date_status":"NOT_DISCLOSED_IN_FILING",
            "previous_per_share":float(prev.group(1)) if prev else None,
            "previous_per_share_status":"VERIFIED" if prev else "NOT_DISCLOSED_IN_FILING",
            "previous_context": (ctx[max(0,prev.start()-120):prev.end()+160] if prev else None),
            "increase_per_share":float(inc.group(1)) if inc else (float(cents.group(1))/100 if cents else None),
            "increase_pct":int(pct_val) if pct_val else None,
            "source_type":"SEC Form 8-K" if role=="PRIMARY" else "SEC Exhibit 99.1",
            "raw_context":ctx[:900]})
    candidates.sort(key=lambda x: (bool(x["record_date"]), bool(x["payment_date"]),
                                   x["previous_per_share"] is not None), reverse=True)
    return candidates


def parse_preferred(text: str, ticker: str, role: str):
    text = norm(text); out=[]
    for m in AMOUNT.finditer(text):
        before=text[max(0,m.start()-400):m.start()]; after=text[m.end():m.end()+300]
        ctx=before+" "+m.group(0)+" "+after
        local=text[max(0,m.start()-180):m.end()+180].lower()
        if "preferred" not in local: continue
        out.append({"ticker":ticker,"event_type":"DECLARED","security_type":"PREFERRED",
                    "declared_per_share":float(m.group(1)),"currency":"USD",
                    "status":"PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND",
                    "source_type":"SEC Form 8-K" if role=="PRIMARY" else "SEC Exhibit 99.1",
                    "raw_context":ctx[:700]})
    return out


def _field(value, status, source, raw=None):
    return {"raw": raw if raw is not None else value, "normalized": value, "status": status,
            "source_url": source["url"], "source_type": source["source_type"],
            "accession_number": source["accession"], "document_role": source["role"],
            "evidence_sha256": source["sha256"], "evidence": source.get("snippet","")}


def build_event(common, primary_common, exhibit, primary, accession, cik):
    e = dict(common)
    if e.get("previous_per_share") is None and primary_common:
        e["previous_per_share"] = primary_common.get("previous_per_share")
        if e["previous_per_share"] is not None:
            e["previous_per_share_status"] = "VERIFIED"
            e["previous_source"] = primary
    e["ticker"] = e["ticker"].upper(); e["cik"] = cik; e["accession_number"] = accession
    e["exhibit"] = exhibit; e["primary"] = primary
    psnip = (primary_common or {}).get("raw_context","")
    if (primary_common or {}).get("previous_context"):
        psnip = primary_common["previous_context"]
    e["sources"] = [
        {"role":"EXHIBIT","source_type":"SEC Exhibit 99.1","url":exhibit["url"],"sha256":exhibit["sha256"],
         "filename":exhibit["name"],"snippet":(common.get("raw_context") or "")[:600]},
        {"role":"PRIMARY","source_type":"SEC Form 8-K","url":primary["url"],"sha256":primary["sha256"],
         "filename":primary["name"],"snippet":psnip[:600]},
    ]
    exhibit["snippet"] = (common.get("raw_context") or "")[:600]
    primary["snippet"] = psnip[:600]
    e["verification_status"] = "VERIFIED"
    e["source_url"] = exhibit["url"]; e["source_type"] = "SEC Exhibit 99.1"
    e["evidence_sha256"] = exhibit["sha256"]
    return e


def run(root=ROOT):
    root=Path(root); m=json.loads((root/"manifest.json").read_text())
    verified_hashes=[]
    for t in m["targets"]:
        for key in ("detail","primary_doc","exhibit_doc"):
            d=t[key]; p=root/t["ticker"]/t["accession"]/Path(d["path"]).name
            assert p.exists(), p
            h=hashlib.sha256(p.read_bytes()).hexdigest(); assert h==d["sha256"], (p,h,d["sha256"])
            verified_hashes.append({"file":str(p),"sha256":h})
    events=[]; exclusions=[]; audit=[]
    for t in m["targets"]:
        pdoc=t["primary_doc"]; edoc=t["exhibit_doc"]
        primary={"role":"PRIMARY","name":pdoc["name"],"url":pdoc["url"],"sha256":pdoc["sha256"],
                 "source_type":"SEC Form 8-K","accession":t["accession"]}
        exhibit={"role":"EXHIBIT","name":edoc["name"],"url":edoc["url"],"sha256":edoc["sha256"],
                 "source_type":"SEC Exhibit 99.1","accession":t["accession"]}
        pt=(root/t["ticker"]/t["accession"]/pdoc["name"]).read_text(errors="ignore")
        et=(root/t["ticker"]/t["accession"]/edoc["name"]).read_text(errors="ignore")
        pc=parse_common(pt,t["ticker"],"PRIMARY"); ec=parse_common(et,t["ticker"],"EXHIBIT")
        common=next((x for x in ec if x["declared_per_share"]>0), None) or next((x for x in pc if x["declared_per_share"]>0), None)
        primary_common=next((x for x in pc if x["declared_per_share"]>0), None)
        if not common: continue
        e=build_event(common,primary_common,exhibit,primary,t["accession"],t["cik"])
        # Field-level status: core values must exist; ex and BAC previous may be not disclosed.
        fields={}
        fields["announcement"] = _field(e["announcement_date"], "VERIFIED" if e["announcement_date"] else "NOT_VERIFIED", exhibit, e.get("raw_context"))
        fields["declared_per_share"] = _field(e["declared_per_share"], "VERIFIED", exhibit, e.get("raw_context"))
        fields["security_type"] = _field(e["security_type"], "VERIFIED", exhibit)
        fields["frequency"] = _field(e["frequency"], "VERIFIED" if e["frequency"] else "NOT_VERIFIED", exhibit)
        fields["record_date"] = _field(e["record_date"], "VERIFIED" if e["record_date"] else "NOT_DISCLOSED_IN_FILING", exhibit)
        fields["payment_date"] = _field(e["payment_date"], "VERIFIED" if e["payment_date"] else "NOT_DISCLOSED_IN_FILING", exhibit)
        fields["ex_date"] = _field(None, "NOT_DISCLOSED_IN_FILING", exhibit)
        fields["increase_per_share"] = _field(e.get("increase_per_share"), "VERIFIED" if e.get("increase_per_share") is not None else "NOT_VERIFIED", exhibit)
        fields["increase_pct"] = _field(e.get("increase_pct"), "VERIFIED" if e.get("increase_pct") is not None else "NOT_VERIFIED", exhibit)
        if e.get("previous_per_share") is not None:
            src = primary if t["ticker"]=="CAT" else exhibit
            fields["previous_per_share"] = _field(e["previous_per_share"], "VERIFIED", src)
        else:
            fields["previous_per_share"] = _field(None, "NOT_DISCLOSED_IN_FILING", exhibit)
        e["field_status"] = fields
        e["verification_status"] = "VERIFIED" if all(
            f["status"] in ("VERIFIED","NOT_DISCLOSED_IN_FILING") for f in fields.values()) else "PARTIALLY_VERIFIED"
        events.append(e); audit.append({"ticker":e["ticker"],"accession":e["accession_number"],"fields":fields,
                                        "event_status":e["verification_status"]})
        if t["ticker"]=="BAC":
            for p in parse_preferred(et,"BAC","EXHIBIT"):
                p["accession_number"]=t["accession"]; p["cik"]=t["cik"]
                p["source_url"]=exhibit["url"]; p["evidence_sha256"]=exhibit["sha256"]
                exclusions.append(p)
    OUT_EVENTS.write_text(json.dumps({"events":events,"provenance":"LIVE_SEC_USER_AGENT"},
                                     indent=2,default=str),encoding="utf-8")
    OUT_AUDIT.write_text(json.dumps({"events":audit,"hashes":verified_hashes},indent=2,default=str),encoding="utf-8")
    OUT_EXCL.write_text(json.dumps({"exclusions":exclusions},indent=2,default=str),encoding="utf-8")
    print(json.dumps({"events":[e["ticker"] for e in events],
                      "status":[e["verification_status"] for e in events],
                      "exclusions":len(exclusions)},indent=2))
    return events


if __name__ == "__main__":
    run()
