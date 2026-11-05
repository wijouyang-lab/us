"""P6.5: download SEC Submissions bulk and enrich securities with issuer SIC."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, time, urllib.error, urllib.request, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
CURRENT = Path("data/universe/us_equities_current.csv")
MAP = Path("data/universe/sec_sic_model_family_map_p65.csv")
OUT = Path("data/universe/us_equity_industry_sic_p65.csv")
COVERAGE = Path("data/universe/us_equity_industry_coverage_p65.json")
SP500 = Path("sp500_constituents.csv")
SPECIAL = {"BANKS","INSURANCE","OTHER_FINANCIALS","REIT","BDC","UTILITIES","ENERGY"}
STANDARD = {"MATERIALS","INDUSTRIALS","TECHNOLOGY","COMMUNICATIONS","HEALTHCARE",
            "CONSUMER_DISCRETIONARY","CONSUMER_STAPLES","OTHER_SERVICES"}


def ua_status() -> str:
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua: return "SEC_USER_AGENT_NOT_CONFIGURED"
    if "example.com" in ua or "your_" in ua or "@" not in ua or len(ua) < 12:
        return "SEC_USER_AGENT_INVALID"
    return "SEC_USER_AGENT_CONFIGURED"


def download(out: Path, meta_path: Path) -> dict:
    if ua_status() != "SEC_USER_AGENT_CONFIGURED":
        raise RuntimeError("CONFIGURATION_BLOCKED: " + ua_status())
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": os.getenv("SEC_USER_AGENT", ""), "Accept": "*/*"}
    meta = {"url": URL, "started_at": datetime.now(timezone.utc).isoformat()}
    req = urllib.request.Request(URL, method="HEAD", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        meta.update({"head_status": r.status, "content_length": r.headers.get("Content-Length"),
                     "last_modified": r.headers.get("Last-Modified")})
    time.sleep(0.25)
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        meta.update({"get_status": r.status, "content_type": r.headers.get("Content-Type")})
        total = int(r.headers.get("Content-Length") or 0)
        h = hashlib.sha256(); size = 0
        with out.open("wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk: break
                f.write(chunk); h.update(chunk); size += len(chunk)
    meta.update({"downloaded_bytes": size, "sha256": h.hexdigest(),
                 "downloaded_at": datetime.now(timezone.utc).isoformat(),
                 "status": "SIZE_MISMATCH" if total and total != size else "DOWNLOADED"})
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_rules(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rules = list(csv.DictReader(f))
    for r in rules:
        r["sic_min"] = int(r["sic_min"]); r["sic_max"] = int(r["sic_max"]); r["priority"] = int(r["priority"])
    return sorted(rules, key=lambda r: r["priority"])


def model_family(sic: str, description: str, rules: list[dict]) -> tuple[str, str]:
    if not str(sic or "").strip(): return "UNCLASSIFIED", "NO_SIC"
    try: code = int(str(sic).strip())
    except ValueError: return "UNCLASSIFIED", "SIC_NOT_NUMERIC"
    desc = (description or "").upper()
    for r in rules:
        if r["sic_min"] <= code <= r["sic_max"]:
            if r["description_contains"] and r["description_contains"].upper() not in desc:
                continue
            return r["model_family"], r["rule_id"]
    return "OTHER_SERVICES", "FALLBACK_OTHER_SERVICES"


def enrich(zip_path: Path, out_path: Path, coverage_path: Path, map_path: Path = MAP,
           current: Path = CURRENT, sp_path: Path = SP500,
           retrieved_at: str | None = None) -> dict:
    if not zip_path.exists(): raise FileNotFoundError(zip_path)
    rules = load_rules(map_path)
    with current.open(encoding="utf-8") as f: uni = list(csv.DictReader(f))
    target_ciks = {(r.get("CIK") or "").strip().zfill(10) for r in uni if (r.get("CIK") or "").strip()}
    docs = {}
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            m = re.match(r"CIK(\d{10})\.json$", Path(info.filename).name)
            if not m or m.group(1) not in target_ciks: continue
            try:
                with z.open(info) as f: docs[m.group(1)] = json.load(f)
            except Exception:
                docs.pop(m.group(1), None)
    sectors = {}
    if sp_path.exists():
        with sp_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f): sectors[norm(r.get("Ticker",""))] = (r.get("Sector") or "").strip()
    cik_tickers = defaultdict(list)
    for u in uni:
        c = (u.get("CIK") or "").strip().zfill(10)
        if c: cik_tickers[c].append(u["ticker"])
    rows = []
    for u in uni:
        cik = (u.get("CIK") or "").strip().zfill(10) if (u.get("CIK") or "").strip() else ""
        doc = docs.get(cik) if cik else None
        sic = str(doc.get("sic") or "").strip() if doc else ""
        desc = str(doc.get("sicDescription") or "").strip() if doc else ""
        fam, rule = model_family(sic, desc, rules)
        if not cik: fam, rule = "UNCLASSIFIED", "NO_CIK"
        elif not doc: fam, rule = "UNCLASSIFIED", "SEC_SUBMISSIONS_MISSING"
        elif not sic: fam, rule = "UNCLASSIFIED", "NO_SIC"
        addresses = (doc or {}).get("addresses") or {}
        business = addresses.get("business") or {}
        sp_sector = sectors.get(norm(u["ticker"]), "")
        expected = expected_families(sp_sector)
        if not sic: consistency = "MISSING_SIC"
        elif not sp_sector: consistency = "NO_SP500_SECTOR"
        elif expected and fam in expected: consistency = "CONSISTENT"
        elif expected: consistency = "INCONSISTENT"
        else: consistency = "NO_EXPECTED_MAPPING"
        rows.append({
            "ticker": u["ticker"], "security_name": u["security_name"], "exchange": u["exchange"],
            "security_type": u["security_type"], "CIK": cik,
            "entity_name": doc.get("entityName", "") if doc else "",
            "sic": sic, "sic_description": desc,
            "entity_type": doc.get("entityType", "") if doc else "",
            "state_of_incorporation": doc.get("stateOfIncorporation", "") if doc else "",
            "country": business.get("country", "") if doc else "",
            "tickers": ",".join(cik_tickers.get(cik, [])),
            "exchanges": u["exchange"], "model_family": fam, "mapping_rule": rule,
            "sp500_sector": sp_sector, "sp500_consistency": consistency,
            "source_url": (f"https://data.sec.gov/submissions/CIK{cik}.json" if cik else ""),
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        })
    fields = list(rows[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    target = [r for r in rows if r["security_type"] in ("COMMON","ADR")]
    unclass = [r for r in rows if r["security_type"] == "UNCLASSIFIED"]
    with_sic = [r for r in target if r["sic"]]
    ciks_with_sic = {r["CIK"] for r in with_sic if r["CIK"]}
    all_target_ciks = {r["CIK"] for r in target if r["CIK"]}
    by_type = {}
    for typ in ("COMMON","ADR"):
        rs = [r for r in target if r["security_type"] == typ]
        by_type[typ] = {"records": len(rs), "with_sic": sum(1 for r in rs if r["sic"]),
                        "coverage": round(sum(1 for r in rs if r["sic"]) / len(rs), 6) if rs else None}
    by_exchange = {}
    for ex in sorted({r["exchange"] for r in target}):
        rs = [r for r in target if r["exchange"] == ex]
        by_exchange[ex] = {"records": len(rs), "with_sic": sum(1 for r in rs if r["sic"]),
                           "coverage": round(sum(1 for r in rs if r["sic"]) / len(rs), 6)}
    family_counts = Counter(r["model_family"] for r in target)
    consistency = Counter(r["sp500_consistency"] for r in target)
    coverage = {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                     "source": URL, "sic_map": str(map_path), "sic_map_version": "P6.5v1",
                     "scope": "P6.1 current Common + ADR; UNCLASSIFIED separate",
                     "note": "SEC SIC is not GICS. No name-based industry inference."},
        "counts": {"target_records": len(target), "target_with_sic": len(with_sic),
                   "target_missing_sic": len(target) - len(with_sic),
                   "target_with_cik": sum(1 for r in target if r["CIK"]),
                   "target_missing_cik": sum(1 for r in target if not r["CIK"]),
                   "target_unique_ciks": len(all_target_ciks),
                   "unique_ciks_with_sic": len(ciks_with_sic),
                   "unique_ciks_missing_sic": len(all_target_ciks - ciks_with_sic),
                   "sic_code_missing": sum(1 for r in target if not r["sic"]),
                   "sic_description_missing": sum(1 for r in target if r["sic"] and not r["sic_description"]),
                   "unclassified_records": len(unclass),
                   "unclassified_with_sic": sum(1 for r in unclass if r["sic"]),
                   "unclassified_unique_ciks": len({r["CIK"] for r in unclass if r["CIK"]})},
        "by_type": by_type, "by_exchange": by_exchange,
        "model_family_counts": dict(family_counts),
        "special_model_records": sum(family_counts[x] for x in SPECIAL),
        "standard_model_records": sum(family_counts[x] for x in STANDARD),
        "other_financials": family_counts.get("OTHER_FINANCIALS", 0),
        "unclassified": family_counts.get("UNCLASSIFIED", 0),
        "sp500_consistency": dict(consistency),
        "sp500_inconsistent_examples": [{"ticker": r["ticker"], "sic": r["sic"],
            "sic_description": r["sic_description"], "sec_family": r["model_family"],
            "sp500_sector": r["sp500_sector"]} for r in target if r["sp500_consistency"] == "INCONSISTENT"][:50],
        "missing_sic_examples": [{"ticker": r["ticker"], "type": r["security_type"]}
                                  for r in target if not r["sic"]][:100],
    }
    coverage_path.write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    return coverage


def expected_families(sector: str) -> set[str] | None:
    s = (sector or "").lower()
    if not s: return None
    if s == "information technology": return {"TECHNOLOGY"}
    if s == "financials": return {"BANKS","INSURANCE","OTHER_FINANCIALS","REIT","BDC"}
    if s == "real estate": return {"REIT"}
    if s == "utilities": return {"UTILITIES"}
    if s == "energy": return {"ENERGY"}
    if s == "materials": return {"MATERIALS"}
    if s == "industrials": return {"INDUSTRIALS"}
    if s == "health care": return {"HEALTHCARE"}
    if s == "consumer discretionary": return {"CONSUMER_DISCRETIONARY"}
    if s == "consumer staples": return {"CONSUMER_STAPLES"}
    if s == "communication services": return {"COMMUNICATIONS"}
    return None


def norm(v: str) -> str:
    x = re.sub(r"[^A-Z0-9]", ".", str(v or "").upper())
    return re.sub(r"\.+", ".", x).strip(".")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, default=Path("data/sec/submissions_p65.zip"))
    ap.add_argument("--metadata", type=Path, default=Path("data/sec/submissions_p65_meta.json"))
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--coverage", type=Path, default=COVERAGE)
    ap.add_argument("--map", type=Path, default=MAP)
    a = ap.parse_args()
    try:
        if a.download:
            meta = download(a.zip, a.metadata)
            print(json.dumps(meta))
        cov = enrich(a.zip, a.out, a.coverage, a.map, retrieved_at=datetime.now(timezone.utc).isoformat())
        print(json.dumps(cov["counts"], indent=2))
        return 0
    except Exception as exc:
        print(f"P6.5_ENRICHMENT_FAILED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
