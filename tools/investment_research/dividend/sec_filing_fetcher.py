"""Fetch SEC primary documents/exhibits for split evidence. Cache-only output."""
from __future__ import annotations
import hashlib, json, os, re, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.sec.gov/Archives/edgar/data"


def config_status(user_agent: str | None = None) -> str:
    ua = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
    if not ua: return "SEC_USER_AGENT_NOT_CONFIGURED"
    if ("example.com" in ua or "your_" in ua or "@" not in ua or len(ua) < 12):
        return "SEC_USER_AGENT_INVALID"
    return "SEC_USER_AGENT_CONFIGURED"


def archive_dir(cik: str, accession: str) -> str:
    return f"{BASE}/{int(cik)}/{accession.replace('-', '')}"


def index_url(cik: str, accession: str) -> str:
    return archive_dir(cik, accession) + "/index.json"


class FilingFetcher:
    def __init__(self, cache: Path, user_agent: str | None = None, min_interval=0.25):
        ua = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
        if config_status(ua) != "SEC_USER_AGENT_CONFIGURED":
            raise RuntimeError("CONFIGURATION_BLOCKED: " + config_status(ua))
        self.ua = ua; self.cache = Path(cache); self.cache.mkdir(parents=True, exist_ok=True)
        self.min_interval = max(0.25, min_interval); self.last = 0.0

    def _get(self, url: str, dest: Path) -> dict:
        if dest.exists():
            raw = dest.read_bytes()
            return {"status": 200, "cached": True, "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw), "path": str(dest)}
        wait = self.min_interval - (time.monotonic() - self.last)
        if wait > 0: time.sleep(wait)
        self.last = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read(); status = r.status
        except urllib.error.HTTPError as e:
            return {"status": e.code, "error": f"HTTP {e.code}", "url": url}
        except Exception as e:
            return {"status": None, "error": type(e).__name__, "url": url}
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
        return {"status": status, "cached": False, "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw), "path": str(dest), "url": url}

    def fetch_filing(self, ticker: str, cik: str, accession: str) -> dict:
        d = self.cache / accession.replace("-", "")
        idx = self._get(index_url(cik, accession), d / "index.json")
        if idx.get("status") != 200:
            return {"ticker": ticker, "cik": cik, "accession": accession, **idx,
                    "documents": [], "status_text": "INDEX_FETCH_FAILED"}
        data = json.loads((d / "index.json").read_text())
        items = data.get("directory", {}).get("item", [])
        def is_doc(it):
            n = it.get("name", "").lower()
            return n.endswith((".htm", ".html")) and "index" not in n and n[:1] != "r"
        candidates = [it for it in items if is_doc(it)]
        ticker_l = ticker.lower().replace(".", "")
        primary = next((it for it in candidates if ticker_l in it.get("name", "").lower()), None)
        if not primary:
            primary = next((it for it in candidates if it.get("type", "").upper() in ("8-K", "10-K", "10-Q")), None)
        if not primary and candidates: primary = candidates[0]
        selected = []
        if primary: selected.append(("PRIMARY", primary))
        for it in candidates:
            typ = (it.get("type") or "").upper(); desc = (it.get("description") or "").lower()
            if it is primary: continue
            if "EX-99" in typ or "EX-99" in (it.get("name","").upper()) or "press release" in desc or "dividend" in desc:
                selected.append(("EXHIBIT", it))
        docs = []
        for role, it in selected:
            name = it.get("name", "")
            res = self._get(f"{archive_dir(cik, accession)}/{name}", d / name)
            docs.append({"role": role, "name": name, "type": it.get("type"),
                         "description": it.get("description"), "sequence": it.get("sequence"),
                         "url": f"{archive_dir(cik, accession)}/{name}", **res})
        primary_doc = next((x for x in docs if x["role"] == "PRIMARY"), None)
        exhibits = [x for x in docs if x["role"] == "EXHIBIT"]
        primary_ok = bool(primary_doc and primary_doc.get("status") == 200)
        exhibit_fail = any(x.get("status") != 200 for x in exhibits)
        if not primary_ok:
            status = "FETCH_FAILED"
        elif exhibit_fail:
            status = "FETCHED_PARTIAL"
        else:
            status = "FETCHED_COMPLETE"
        return {"ticker": ticker, "cik": cik, "accession": accession,
                "index_url": index_url(cik, accession), "status_text": status,
                "documents": docs, "primary": primary_doc, "exhibits": exhibits,
                "downloaded": sum(1 for x in docs if x.get("status") == 200),
                "failed": sum(1 for x in docs if x.get("status") != 200)}


SPLIT_WORDS = re.compile(r"(stock split|share split|split of|for[- ]one|reverse split)", re.I)
DATE = re.compile(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", re.I)


def extract_split_text(text: str) -> dict:
    clean = re.sub(r"<[^>]+>", " ", text); clean = re.sub(r"\s+", " ", clean)
    ratio = None
    words = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
             "eleven":11,"twelve":12,"fifteen":15,"twenty":20,"thirty":30,"fifty":50}
    def num(x):
        return float(words.get(x.lower(), x)) if x else None
    m = re.search(r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|fifty)[- ]for[- ](\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|fifty)\s*(?:stock\s+)?split", clean, re.I)
    if m:
        ratio = num(m.group(1)) / num(m.group(2))
    elif re.search(r"reverse\s+stock\s+split", clean, re.I):
        m2 = re.search(r"(\d+)[- ]for[- ](\d+)", clean)
        if m2: ratio = float(m2.group(1)) / float(m2.group(2))
    dates = DATE.findall(clean)
    return {"mentions_split": bool(SPLIT_WORDS.search(clean)), "ratio": ratio,
            "dates": dates[:5], "text_excerpt": clean[:500] if SPLIT_WORDS.search(clean) else ""}


def process(evidence_path: str, cache: Path, ua: str):
    rows = json.loads(Path(evidence_path).read_text())
    f = FilingFetcher(cache, ua)
    out = []
    for row in rows:
        for e in row.get("events", []):
            acc = e.get("accession_number")
            if not acc: continue
            fetched = f.fetch_filing(row["ticker"], row["cik"], acc)
            extraction = {}
            if fetched.get("primary") and fetched["primary"].get("path"):
                try: extraction = extract_split_text(Path(fetched["primary"]["path"]).read_text(errors="ignore"))
                except Exception: extraction = {}
            # Effective date is only extracted from official text, never fact end.
            confirmed = bool(extraction.get("ratio") and extraction.get("dates"))
            out.append({"ticker": row["ticker"], "cik": row["cik"], "accession": acc,
                        "filing": fetched, "extraction": extraction,
                        "status": "SPLIT_CONFIRMED" if confirmed else "PARTIALLY_VERIFIED",
                        "retrieved_at": datetime.now(timezone.utc).isoformat()})
    Path("data/research/split_evidence_p43.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def main():
    import sys
    if "--check-config" in sys.argv:
        print(config_status())
        return
    if config_status() != "SEC_USER_AGENT_CONFIGURED":
        print("CONFIGURATION_BLOCKED: " + config_status())
        return
    rows = process("data/research/split_evidence_p42.json", Path("data/sec/filings_p45"),
                   os.getenv("SEC_USER_AGENT", ""))
    print("processed", len(rows), "split records")

if __name__ == "__main__":
    main()
