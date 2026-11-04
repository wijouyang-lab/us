"""P4.5 targeted CAT/BAC SEC smoke: exactly two detail pages and four files.

No ticker_map()/submissions(), no full scan, no event verification.
"""
from __future__ import annotations
import hashlib, html, json, os, re, sys, time
import urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tools.investment_research.dividend.sec_filing_fetcher import config_status
from tools.investment_research.sec.rate_limiter import get_rate_limiter

OUT = Path("data/sec/filings_p45_smoke")
TARGETS = [
    {"ticker":"CAT","cik":"0000018230","accession":"0001104659-26-072929",
     "detail":"https://www.sec.gov/Archives/edgar/data/18230/000110465926072929/0001104659-26-072929-index.html",
     "primary":"tm2617177d1_8k.htm","exhibit":"tm2617177d1_ex99-1.htm"},
    {"ticker":"BAC","cik":"0000070858","accession":"0000070858-26-000364",
     "detail":"https://www.sec.gov/Archives/edgar/data/70858/000007085826000364/0000070858-26-000364-index.html",
     "primary":"bac-20260723.htm","exhibit":"exhibit991.htm"},
]
BLOCK_MARKERS = ("request rate threshold exceeded", "undeclared automated tool",
                 "your request originates", "too many requests", "access denied")


def is_sec_rejection(text: str) -> bool:
    low = text.lower()
    return any(x in low for x in BLOCK_MARKERS)


def parse_detail(html_text: str) -> dict:
    """Return filename -> set of types from the Filing Detail table."""
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.I | re.S):
        raw_cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.I | re.S)
        cells = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip() for c in raw_cells]
        types = {x.upper() for x in cells if x.upper() in ("8-K", "10-K", "10-Q", "EX-99.1", "EX-99.2")}
        for c in raw_cells:
            href = re.search(r'href="([^"]+)"', c, re.I)
            if not href: continue
            name = href.group(1).rstrip("/").split("/")[-1]
            if types: out.setdefault(name, set()).update(types)
    return out


def _get(url: str, dest: Path, ua: str, limiter, request_log: list) -> dict:
    get_rate_limiter().min_interval = 0.5
    limiter.wait()
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status = r.status; ctype = r.headers.get("Content-Type","")
            raw = r.read()
    except urllib.error.HTTPError as e:
        return {"url":url,"status":e.code,"content_type":None,"bytes":0,"sha256":None,
                "error":f"HTTP {e.code}"}
    except Exception as e:
        return {"url":url,"status":None,"content_type":None,"bytes":0,"sha256":None,
                "error":type(e).__name__}
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    text = raw.decode("utf-8","ignore")
    rec = {"url":url,"status":status,"content_type":ctype,"bytes":len(raw),
           "sha256":hashlib.sha256(raw).hexdigest(),"path":str(dest),
           "downloaded_at":datetime.now(timezone.utc).isoformat(),
           "sec_rejection":is_sec_rejection(text),"cache_hit":False,"real_download":True}
    request_log.append(rec); return rec


def run(out=OUT, ua=None):
    ua = (ua or os.getenv("SEC_USER_AGENT","")).strip()
    if config_status(ua) != "SEC_USER_AGENT_CONFIGURED":
        return {"status":"CONFIGURATION_BLOCKED","config":config_status(ua),"requests":0}
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at":datetime.now(timezone.utc).isoformat(), "status":"DOWNLOAD_PARTIAL",
                "provenance":"LIVE_SEC_USER_AGENT","targets":[],"request_count":0,"requests":[]}
    limiter = get_rate_limiter()
    for t in TARGETS:
        td = out / t["ticker"] / t["accession"]; td.mkdir(parents=True, exist_ok=True)
        detail_path = td / "filing-detail.html"
        detail = _get(t["detail"], detail_path, ua, limiter, manifest["requests"])
        manifest["request_count"] += 1
        target = {**t, "detail": detail, "primary_doc": None, "exhibit_doc": None}
        if detail.get("status") != 200 or detail.get("sec_rejection") or not detail.get("sha256"):
            target["status"] = "DETAIL_FAILED"; manifest["targets"].append(target); continue
        found = parse_detail((td/"filing-detail.html").read_text(errors="ignore"))
        for role, name, expected in (("primary",t["primary"],"8-K"),("exhibit",t["exhibit"],"EX-99.1")):
            types = found.get(name, set())
            if expected not in types:
                target[f"{role}_type"] = sorted(types)
                target[f"{role}_doc"] = {"status":"TYPE_MISMATCH","expected_type":expected,
                                         "found_types":sorted(types),"name":name}
                continue
            url = t["detail"].rsplit("/",1)[0] + "/" + name
            doc = _get(url, td/name, ua, limiter, manifest["requests"])
            manifest["request_count"] += 1
            doc["ticker"]=t["ticker"]; doc["cik"]=t["cik"]; doc["accession"]=t["accession"]
            doc["role"]=role; doc["name"]=name; doc["expected_type"]=expected
            target[f"{role}_doc"] = doc
            if doc.get("status") != 200 or doc.get("sec_rejection") or not doc.get("sha256"):
                target["status"] = "DOWNLOAD_FAILED"
        if target.get("primary_doc") and target.get("exhibit_doc") \
                and all(target[f"{r}_doc"].get("status")==200 and target[f"{r}_doc"].get("sha256")
                        and not target[f"{r}_doc"].get("sec_rejection") for r in ("primary","exhibit")):
            target["status"] = "DOWNLOAD_COMPLETE"
        else:
            target.setdefault("status","DOWNLOAD_PARTIAL")
        manifest["targets"].append(target)
    manifest["status"] = "DOWNLOAD_COMPLETE" if all(t["status"]=="DOWNLOAD_COMPLETE" for t in manifest["targets"]) else "DOWNLOAD_PARTIAL"
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status":manifest["status"],"request_count":manifest["request_count"],
                      "targets":{t["ticker"]:t["status"] for t in manifest["targets"]}}, indent=2))
    return manifest


if __name__ == "__main__":
    m = run()
    sys.exit(0 if m.get("status") == "DOWNLOAD_COMPLETE" else 1)
