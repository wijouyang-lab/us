"""Normalize SEC CompanyFacts bulk ZIP into a long PIT-safe fundamentals panel."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, re, zipfile
from datetime import date, datetime, timezone
from pathlib import Path
import pandas as pd

CURRENT = Path("data/universe/us_equities_current.csv")
ZIP = Path("data/sec/companyfacts_p63.zip")
MAP = Path("data/universe/sec_fundamentals_metric_map_p63.json")
OUT = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
META = Path("data/universe/sec_fundamentals_panel_p63_meta.json")


def _date(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def classify_period(start, end, form):
    if not start: return "INSTANT"
    try:
        days = (date.fromisoformat(str(end)[:10]) - date.fromisoformat(str(start)[:10])).days
    except (TypeError, ValueError):
        return "OTHER"
    if form in ("10-K", "20-F", "40-F") and 300 <= days <= 400: return "ANNUAL"
    if form in ("10-Q", "6-K"):
        if 80 <= days <= 110: return "QUARTER"
        if 160 <= days <= 290: return "YTD"
    if 300 <= days <= 400: return "ANNUAL"
    if 80 <= days <= 110: return "QUARTER"
    return "OTHER"


def next_weekday(v):
    d = _date(v)
    if not d: return None
    return (pd.Timestamp(d) + pd.offsets.BDay(1)).date().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, default=ZIP)
    ap.add_argument("--universe", type=Path, default=CURRENT)
    ap.add_argument("--metric-map", type=Path, default=MAP)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--meta", type=Path, default=META)
    a = ap.parse_args()
    if not a.zip.exists(): print("missing companyfacts ZIP"); return 2
    with a.universe.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    target = [r for r in rows if r["security_type"] in ("COMMON", "ADR") and r.get("CIK")]
    by_cik = {}
    for r in target: by_cik.setdefault(r["CIK"].zfill(10), []).append(r["ticker"])
    # include UNCLASSIFIED only for separate coverage, but parse same CIK once
    for r in rows:
        if r["security_type"] == "UNCLASSIFIED" and r.get("CIK"):
            by_cik.setdefault(r["CIK"].zfill(10), []).append(r["ticker"])
    metric_map = json.loads(a.metric_map.read_text(encoding="utf-8"))
    tag_map = {}
    for metric, taxmap in metric_map.items():
        for tax, tags in taxmap.items():
            for tag in tags: tag_map[(tax, tag)] = metric
    counts = {"target_records": len(target), "unique_ciks": len({r["CIK"].zfill(10) for r in target}),
              "zip_entries": 0, "parsed_ciks": 0, "standard_fact_ciks": 0,
              "us_gaap_ciks": 0, "ifrs_ciks": 0, "missing_ciks": 0, "panel_rows": 0}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    found = set()
    with zipfile.ZipFile(a.zip) as z, gzip.open(a.out, "wt", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=["cik", "entity_name", "tickers", "metric", "taxonomy", "tag", "unit",
                           "value", "start", "end", "filed", "accn", "form", "fy", "fp", "frame",
                           "period_type", "pit_available_date", "pit_rule"])
        w.writeheader()
        for info in z.infolist():
            name = Path(info.filename).name
            m = re.match(r"CIK(\d{10})\.json$", name)
            if not m: continue
            counts["zip_entries"] += 1
            cik = m.group(1)
            if cik not in by_cik: continue
            found.add(cik); counts["parsed_ciks"] += 1
            try:
                with z.open(info) as f: doc = json.load(f)
            except Exception:
                counts["missing_ciks"] += 1; continue
            entity = doc.get("entityName", "")
            taxs = doc.get("facts", {})
            has_std = False; has_us = False; has_ifrs = False
            for tax in ("us-gaap", "ifrs-full", "dei", "srt"):
                for tag, body in (taxs.get(tax) or {}).items():
                    if (tax, tag) not in tag_map: continue
                    metric = tag_map[(tax, tag)]
                    has_std = True
                    if tax == "us-gaap": has_us = True
                    if tax == "ifrs-full": has_ifrs = True
                    for unit, facts in (body.get("units") or {}).items():
                        for fact in facts:
                            end = fact.get("end"); filed = fact.get("filed")
                            value = fact.get("val")
                            if value is None: continue
                            ed = _date(end) or _date(filed)
                            if not ed or ed < date(2016, 1, 1): continue
                            start = fact.get("start")
                            w.writerow({"cik": cik, "entity_name": entity,
                                "tickers": "|".join(sorted(set(by_cik[cik]))),
                                "metric": metric, "taxonomy": tax, "tag": tag, "unit": unit,
                                "value": value, "start": start or "", "end": end or "",
                                "filed": filed or "", "accn": fact.get("accn") or "",
                                "form": fact.get("form") or "", "fy": fact.get("fy") or "",
                                "fp": fact.get("fp") or "", "frame": fact.get("frame") or "",
                                "period_type": classify_period(start, end, fact.get("form")),
                                "pit_available_date": next_weekday(filed),
                                "pit_rule": "NEXT_WEEKDAY_AFTER_FILED; holidays not adjusted"})
                            counts["panel_rows"] += 1
            if has_std: counts["standard_fact_ciks"] += 1
            if has_us: counts["us_gaap_ciks"] += 1
            if has_ifrs: counts["ifrs_ciks"] += 1
    counts["missing_ciks"] = len(set(by_cik) - found)
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(), "zip": str(a.zip),
            "zip_sha256": hashlib.sha256(a.zip.read_bytes()).hexdigest(),
            "zip_bytes": a.zip.stat().st_size, "counts": counts,
            "pit_rule": "filed -> next weekday; no holiday adjustment; no acceptanceDateTime",
            "note": "Restatements are retained as separate accn rows; Q2/Q3 YTD is not relabeled as quarter."}
    a.meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
