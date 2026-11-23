#!/usr/bin/env python3
"""P17.2.8.3.3 cache inventory and strict closeout validation, offline."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from lxml import html

ET = ZoneInfo("America/New_York")
P27 = Path("../default-workspace/_us_p1727/data/research/p17_2_7/cache")
P281 = Path("../default-workspace/_us_p17281/data/research/p17_2_8_1/cache")
ROWS = Path("../default-workspace/_us_p172832/data/research/p17_2_8_3_2/row_level_reconciliation.csv")


def cik10(v):
    s = re.sub(r"\.0$", "", str(v)).strip()
    return s.zfill(10) if s.isdigit() else ""


def parse(path):
    root = html.parse(str(path)).getroot()
    ctx = {}
    for c in root.xpath("//*[contains(local-name(),'context')]"):
        ident = c.xpath(".//*[contains(local-name(),'identifier')]/text()")
        dims = [f"{m.get('dimension','')}={m.text or ''}" for m in c.xpath(".//*[contains(local-name(),'explicitmember')]")]
        ctx[c.get('id')] = {"cik": cik10(ident[0]) if ident else "", "dims": ";".join(dims)}
    by = {}
    for el in root.xpath("//*[contains(local-name(),'nonnumeric')]"):
        local = (el.get('name') or '').split(':')[-1]
        if local in {"TradingSymbol", "Security12bTitle", "Security12gTitle", "SecurityExchangeName"}:
            by.setdefault(el.get('contextRef') or el.get('contextref') or '', {}).setdefault(local, []).append(re.sub(r"\s+", " ", el.text or "").strip())
    return ctx, by


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()): raise SystemExit("REFUSING_NONEMPTY_OUTPUT")
    a.out.mkdir(parents=True, exist_ok=True)
    inv = []; subs = {}; accessions = []
    for d in [P27, P281]:
        for f in d.iterdir():
            b = f.read_bytes(); typ = "JSON" if b.lstrip().startswith(b"{") else "HTML" if b.lstrip().startswith(b"<") else "OTHER"
            inv.append({"path": str(f), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "type": typ})
            if typ == "JSON":
                try:
                    j = json.loads(b)
                    if "filings" in j:
                        cik = cik10(j.get("cik", "")); subs[cik] = j
                        rec = j["filings"].get("recent", {})
                        for acc, form, fd, ad, doc in zip(rec.get("accessionNumber", []), rec.get("form", []), rec.get("filingDate", []), rec.get("acceptanceDateTime", []), rec.get("primaryDocument", [])):
                            accessions.append({"cik": cik, "accession": acc, "form": form, "filing_date": fd, "acceptance": ad, "primary": doc,
                                               "tickers": ",".join([x for x in (j.get("tickers") or []) if isinstance(x, str)])})
                except Exception:
                    pass
    pd.DataFrame(inv).to_csv(a.out / "cache_inventory.csv", index=False)
    acc = pd.DataFrame(accessions).drop_duplicates(["cik", "accession"])
    acc.to_csv(a.out / "cache_accession_inventory.csv", index=False)
    rows = pd.read_csv(ROWS, dtype=str)
    # Recovery: try submissions whose ticker list contains sample ticker, pick prior 10-K/Q, check cached doc if known.
    recovered = []
    for _, r in rows.iterrows():
        if r.independent_status == "VERIFIED_RECONFIRMED": continue
        if not r.ticker: continue
        cands = [c for c, j in subs.items() if r.ticker in [x for x in (j.get("tickers") or []) if isinstance(x, str)]]
        for c in cands:
            rec = subs[c].get("filings", {}).get("recent", {})
            for ac, form, ad, doc in zip(rec.get("accessionNumber", []), rec.get("form", []), rec.get("acceptanceDateTime", []), rec.get("primaryDocument", [])):
                if form not in ("10-K", "10-Q"): continue
                if ac == r.accession: continue
                try: at = pd.to_datetime(ad, utc=True)
                except Exception: continue
                cutoff = pd.Timestamp(r.anchor_date).tz_localize(ET).replace(hour=16).tz_convert("UTC")
                if pd.isna(at) or at > cutoff: continue
                url = f"https://www.sec.gov/Archives/edgar/data/{int(c)}/{ac.replace('-', '')}/{doc}"
                p = None
                for d in [P27, P281]:
                    q = d / hashlib.sha256(url.encode()).hexdigest()
                    if q.exists(): p = q; break
                if not p: continue
                ctx, by = parse(p); hits = [(cid, v) for cid, v in by.items() if r.ticker in v.get("TradingSymbol", [])]
                if not hits: continue
                target_titles = [(v.get("Security12bTitle", []) + v.get("Security12gTitle", [])) for cid, v in hits]
                if any(not any(t) for t in target_titles): continue
                titles = {x for t in target_titles for x in t if x}
                cik = ctx.get(hits[0][0], {}).get("cik", "")
                if len(titles) == 1 and cik == c:
                    recovered.append({"anchor": r.anchor, "ticker": r.ticker, "candidate_cik": c, "accession": ac,
                                      "acceptance": at.isoformat(), "security_title": next(iter(titles)), "status": "RECOVERABLE_VERIFIED"})
                    break
    rec = pd.DataFrame(recovered)
    rec.to_csv(a.out / "cached_filing_recovery.csv", index=False)
    # Crosswalk of accessions to sample tickers (current only).
    cross = []
    for _, r in rows.iterrows():
        for c, j in subs.items():
            if r.ticker in [x for x in (j.get("tickers") or []) if isinstance(x, str)]:
                cross.append({"anchor": r.anchor, "ticker": r.ticker, "cache_cik": c, "source": "submissions_tickers"})
    pd.DataFrame(cross).to_csv(a.out / "cache_accession_crosswalk.csv", index=False)
    # Classification: preserve verified, split 41 by candidate.
    classified = rows.copy()
    classified["new_status"] = classified.independent_status
    mask = classified.new_status.isin(["NO_HISTORICAL_CIK_CANDIDATE", "NO_HISTORICAL_FILING"])
    classified.loc[mask, "new_status"] = [
        "NO_HISTORICAL_FILING" if (pd.notna(v) and str(v) != "") else "NO_HISTORICAL_CIK_CANDIDATE"
        for v in classified.loc[mask, "selected_cik"]]
    classified.to_csv(a.out / "row_level_classification_adjudication.csv", index=False)
    # 235 context audit: use independent fields already generated.
    v = classified[classified.new_status == "VERIFIED_RECONFIRMED"].copy()
    v["context_match"] = v.context_entity_cik == v.selected_cik
    v["title_present"] = v.independent_title.notna() & (v.independent_title != "")
    v.to_csv(a.out / "verified_235_context_audit.csv", index=False)
    ex = v[~(v.context_match & v.title_present)]
    ex.to_csv(a.out / "verified_235_exception_review.csv", index=False)
    anchor = classified.groupby(["anchor", "anchor_date"]).agg(total=("ticker", "size"),
        verified=("new_status", lambda x: (x == "VERIFIED_RECONFIRMED").sum())).reset_index()
    summary = {"cache_files": len(inv), "submissions": len(subs), "accessions": len(acc),
               "samples": len(classified), "verified": int((classified.new_status == "VERIFIED_RECONFIRMED").sum()),
               "status": classified.new_status.value_counts().to_dict(), "recovered": len(rec),
               "anchor": anchor.to_dict("records"), "network_requests": 0,
               "business_sha256": hashlib.sha256((a.out / "row_level_classification_adjudication.csv").read_bytes()).hexdigest()}
    (a.out / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    im = {"rows": {"path": str(ROWS), "sha256": hashlib.sha256(ROWS.read_bytes()).hexdigest()},
          "cache_files": [{"path": x["path"], "sha256": x["sha256"], "bytes": x["bytes"]} for x in inv]}
    (a.out / "input_manifest.json").write_text(json.dumps(im, indent=2), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"} and p.name != "output_manifest.json":
            files[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    (a.out / "output_manifest.json").write_text(json.dumps({"outputs": files, "business_sha256": summary["business_sha256"]}, indent=2), encoding="utf-8")
    (a.out / "clean_replay_comparison.json").write_text(json.dumps({"run1": summary["business_sha256"], "run2": "PENDING"}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()


